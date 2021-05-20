# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2021 Opener B.V. (<https://opener.amsterdam>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, MONTHLY, WEEKLY, YEARLY, rrule

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import safe_eval


class DateRangeGenerator(models.TransientModel):
    _name = 'date.range.generator'
    _description = 'Date Range Generator'

    @api.model
    def _default_company(self):
        return self.env['res.company']._company_default_get('date.range')

    name_expr = fields.Text(
        "Range name expression",
        help=("Evaluated expression. E.g. "
              "\"'FY%s' % date_start.strftime('%Y%m%d')\"\nYou can "
              "use the Date types 'date_end' and 'date_start', as well as "
              "the 'index' variable."))
    name_prefix = fields.Char('Range name prefix')
    date_start = fields.Date("Start date", required=True)
    date_end = fields.Date("End date")
    type_id = fields.Many2one(
        comodel_name='date.range.type', string='Type', required=True,
        domain="['|', ('company_id', '=', company_id), "
               "('company_id', '=', False)]", ondelete='cascade')
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company',
        default=_default_company)
    unit_of_time = fields.Selection([
        (str(YEARLY), 'years'),
        (str(MONTHLY), 'months'),
        (str(WEEKLY), 'weeks'),
        (str(DAILY), 'days')], required=True)
    duration_count = fields.Integer('Duration', required=True)
    count = fields.Integer(
        string="Number of ranges to generate", required=True)

    @api.onchange("date_end")
    def onchange_date_end(self):
        if self.date_end and self.count:
            self.count = 0

    @api.onchange("count")
    def onchange_count(self):
        if self.count and self.date_end:
            self.date_end = False

    @api.onchange("name_expr")
    def onchange_name_expr(self):
        """Wipe the prefix if an expression is entered.

        The reverse is not implemented because we don't want to wipe the
        users' painstakingly crafted expressions by accident.
        """
        if self.name_expr and self.name_prefix:
            self.name_prefix = False

    @api.multi
    def _generate_intervals(self):
        """Generate a list of dates representing the intervals.

        The last date only serves to compute the end date of the last interval.
        """
        if not self.date_end and not self.count:
            raise ValidationError(
                _("Please enter an end date, or the number of ranges to "
                  "generate."))
        kwargs = dict(
            freq=int(self.unit_of_time),
            interval=self.duration_count,
            dtstart=self.date_start
        )
        if self.date_end:
            kwargs["until"] = self.date_end
        else:
            kwargs["count"] = self.count
        vals = list(rrule(**kwargs))
        if not vals:
            raise UserError("No ranges to generate with these settings")
        # Generate another interval to fetch the last end date from
        vals.append(
            list(
                rrule(
                    freq=int(self.unit_of_time),
                    interval=self.duration_count,
                    dtstart=vals[-1].date(),
                    count=2,
                ))[-1])
        return vals

    @api.multi
    def generate_names(self, vals):
        """Generate the names for the given intervals"""
        self.ensure_one()
        return self._generate_names(vals, self.name_expr, self.name_prefix)

    @staticmethod
    def _generate_names(vals, name_expr, name_prefix):
        """Generate the names for the given intervals and naming parameters"""
        names = []
        count_digits = len(str(len(vals)))
        for idx, dt_start in enumerate(vals[:-1]):
            date_start = dt_start.date()
            # always remove 1 day for the date_end since range limits are
            # inclusive
            date_end = vals[idx+1].date() - relativedelta(days=1)
            index = "%0*d" % (count_digits, idx + 1)
            if name_expr:
                try:
                    names.append(safe_eval(
                        name_expr, {
                            "date_end": date_end,
                            "date_start": date_start,
                            "index": index,
                        }))
                except SyntaxError as e:
                    raise ValidationError(_("Invalid name expression: %s") % e)
            elif name_prefix:
                names.append(name_prefix + index)
            else:
                raise ValidationError(
                    _("Please set a prefix or an expression to generate "
                      "the range names."))
        return names

    def test_name_expr(self):
        """Button on the form to preview the generated names"""
        self.ensure_one()
        names = self.generate_names(self._generate_intervals())
        raise UserError("\n".join(names))

    def _compute_date_ranges(self):
        """Actually generate the date ranges"""
        self.ensure_one()
        vals = self._generate_intervals()
        date_ranges = []
        names = self.generate_names(vals)
        for idx, dt_start in enumerate(vals[:-1]):
            date_start = dt_start.date()
            date_end = vals[idx+1].date() - relativedelta(days=1)
            date_ranges.append({
                'name': names[idx],
                'date_start': date_start,
                'date_end': date_end,
                'type_id': self.type_id.id,
                'company_id': self.company_id.id})
        return date_ranges

    @api.onchange("type_id")
    def _onchange_type_id(self):
        """Take defaults from the type_id"""
        if not self.type_id:
            return
        self.company_id = self.type_id.company_id
        if self.type_id.name_expr:
            self.name_expr = self.type_id.name_expr
        if self.type_id.name_prefix:
            self.name_prefix = self.type_id.name_prefix
        if self.type_id.duration_count:
            self.duration_count = self.type_id.duration_count
        if self.type_id.unit_of_time:
            self.unit_of_time = self.type_id.unit_of_time
        last = self.env["date.range"].search(
            [("type_id", "=", self.type_id.id)],
            order="date_end desc", limit=1)
        today = fields.Date.context_today(self)
        if last:
            self.date_start = last.date_end + relativedelta(days=1)
        elif self.type_id.autogeneration_date_start:
            self.date_start = self.type_id.autogeneration_date_start
        else:  # default to the beginning of the current year
            self.date_start = today.replace(day=1, month=1)
        if (self.type_id.autogeneration_unit and
                self.type_id.autogeneration_count):
            key = {
                str(YEARLY): "years",
                str(MONTHLY): "months",
                str(WEEKLY): "weeks",
                str(DAILY): "days",
            }[self.type_id.autogeneration_unit]
            date_end = today + relativedelta(
                **{key: self.type_id.autogeneration_count})
            if date_end > self.date_start:
                self.date_end = date_end

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id and self.type_id.company_id and \
                self.type_id.company_id != self.company_id:
            self._cache.update(
                self._convert_to_cache({'type_id': False}, update=True))

    @api.multi
    @api.constrains('company_id', 'type_id')
    def _check_company_id_type_id(self):
        for rec in self.sudo():
            if rec.company_id and rec.type_id.company_id and\
                    rec.company_id != rec.type_id.company_id:
                raise ValidationError(
                    _('The Company in the Date Range Generator and in '
                      'Date Range Type must be the same.'))

    @api.multi
    def action_apply(self):
        date_ranges = self._compute_date_ranges()
        if date_ranges:
            for dr in date_ranges:
                self.env['date.range'].create(dr)
        return self.env['ir.actions.act_window'].for_xml_id(
            module='date_range', xml_id='date_range_action')
