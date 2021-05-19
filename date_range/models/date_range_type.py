# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, MONTHLY, WEEKLY, YEARLY

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form


class DateRangeType(models.Model):
    _name = "date.range.type"
    _description = "Date Range Type"

    @api.model
    def _default_company(self):
        return self.env['res.company']._company_default_get('date.range')

    name = fields.Char(required=True, translate=True)
    allow_overlap = fields.Boolean(
        help="If sets date range of same type must not overlap.",
        default=False)
    active = fields.Boolean(
        help="The active field allows you to hide the date range type "
        "without removing it.", default=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', index=1,
        default=_default_company)
    date_range_ids = fields.One2many('date.range', 'type_id', string='Ranges')

    # Defaults for generating date ranges
    name_expr = fields.Text(
        "Range name expression",
        help=("Evaluated expression. E.g. "
              "\"'FY%s' % date_start.strftime('%Y%m%d')\"\nYou can "
              "use the Date types 'date_end' and 'date_start', as well as "
              "the 'index' variable."))
    name_prefix = fields.Char("Range name prefix")
    duration_count = fields.Integer("Duration")
    unit_of_time = fields.Selection([
        (str(YEARLY), "years"),
        (str(MONTHLY), "months"),
        (str(WEEKLY), "weeks"),
        (str(DAILY), "days")])
    autogeneration_count = fields.Integer()
    autogeneration_unit = fields.Selection([
        (str(YEARLY), "years"),
        (str(MONTHLY), "months"),
        (str(WEEKLY), "weeks"),
        (str(DAILY), "days")])

    _sql_constraints = [
        ('date_range_type_uniq', 'unique (name,company_id)',
         'A date range type must be unique per company !')]

    @api.constrains('company_id')
    def _check_company_id(self):
        if not self.env.context.get('bypass_company_validation', False):
            for rec in self.sudo():
                if not rec.company_id:
                    continue
                if bool(rec.date_range_ids.filtered(
                        lambda r: r.company_id and
                        r.company_id != rec.company_id)):
                    raise ValidationError(
                        _('You cannot change the company, as this '
                          'Date Range Type is  assigned to Date Range '
                          '(%s).') % (rec.date_range_ids.name_get()[0][1]))

    @api.onchange("name_expr")
    def onchange_name_expr(self):
        """Wipe the prefix if an expression is entered.

        The reverse is not implemented because we don't want to wipe the
        users' painstakingly crafted expressions by accident.
        """
        if self.name_expr and self.name_prefix:
            self.name_prefix = False

    def test_name_expr(self):
        """Button on the form to preview newly generated names"""
        self.ensure_one()
        year_start = fields.Datetime.now().replace(day=1, month=1)
        next_year = year_start + relativedelta(years=1)
        names = self.env["date.range.generator"]._generate_names(
            [year_start, next_year], self.name_expr, self.name_prefix)
        raise UserError("\n".join(names))

    @api.model
    def autogenerate_ranges(self):
        """Generate ranges for types with autogeneration settings"""
        for dr_type in self.search(
                [("autogeneration_count", "!=", False),
                 ("autogeneration_unit", "!=", False)]):
            try:
                with self.env.cr.savepoint():
                    form = Form(self.env["date.range.generator"])
                    form.type_id = dr_type
                    wizard = form.save()
                    wizard.action_apply()
            except (AssertionError, UserError, ValidationError):
                pass
