# Copyright 2021 Opener B.V. <stefan@opener.amsterdam>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from lxml import etree
from psycopg2 import sql

from odoo.osv.expression import (
    NEGATIVE_TERM_OPERATORS, TRUE_DOMAIN, FALSE_DOMAIN
)
from odoo import _, api, fields, models


class DateRangeSearchMixin(models.AbstractModel):
    _name = "date.range.search.mixin"
    _description = "Mixin class to add a Many2one style period search field"
    # Override this attribute to apply the mixin to another field
    _date_range_search_field = "date"
    # Set this attribute to assign a date range of the type with this code.
    # This has to be a date range type without company set
    _date_range_assign_type_code = None

    date_range_search_id = fields.Many2one(
        comodel_name="date.range",
        string="Filter by period (technical field)",
        compute="_compute_date_range_search_id",
        search="_search_date_range_search_id")

    def _compute_date_range_search_id(self):
        """Assign a value for the computed field.

        This can either a matching date range from the specified type,
        if any, or False.
        """
        record2range = {}
        if self._date_range_assign_type_code:
            dr_type = self.env["date.range.type"].search(
                [("code", "=", self._date_range_assign_type_code),
                 ("company_id", "=", False)], limit=1)
            if dr_type:
                query = sql.SQL(
                    """
                    SELECT tbl.id, dr.id
                    FROM {} AS tbl
                    JOIN date_range AS dr
                        ON {} BETWEEN dr.date_start AND dr.date_end
                    WHERE dr.type_id = %s AND tbl.id IN %s
                    """).format(
                        sql.Identifier(self._table),
                        sql.Identifier(self._date_range_search_field),
                    )
                self.env.cr.execute(
                    query,
                    (dr_type.id, tuple(self.ids or [0])),
                )
                record2range = dict(self.env.cr.fetchall())
        for record in self:
            record.date_range_search_id = record2range.get(record.id)

    @api.model
    def _search_date_range_search_id(self, operator, value):
        """Map the selected date ranges to the model's date field"""
        # Deal with some bogus values
        if not value:
            if operator in NEGATIVE_TERM_OPERATORS:
                return TRUE_DOMAIN
            return FALSE_DOMAIN
        if value is True:
            if operator in NEGATIVE_TERM_OPERATORS:
                return FALSE_DOMAIN
            return TRUE_DOMAIN
        # Assume from here on that the value is a string,
        # a single id or a list of ids
        ranges = self.env["date.range"]
        if isinstance(value, str):
            ranges = self.env["date.range"].search(
                [("name", operator, value)])
        else:
            if isinstance(value, int):
                value = [value]
            sub_op = "not in" if operator in NEGATIVE_TERM_OPERATORS else "in"
            ranges = self.env["date.range"].search([("id", sub_op, value)])
        if not ranges:
            return FALSE_DOMAIN
        domain = (len(ranges) - 1) * ["|"] + sum(
            (["&",
              (self._date_range_search_field, ">=", date_range.date_start),
              (self._date_range_search_field, "<=", date_range.date_end)]
             for date_range in ranges),
            [])
        return domain

    @api.model
    def fields_view_get(
            self, view_id=None, view_type='form', toolbar=False,
            submenu=False):
        """Inject the dummy Many2one field in the search view"""
        result = super().fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar,
            submenu=submenu)
        if view_type != "search":
            return result
        root = etree.fromstring(result["arch"])
        if root.xpath("//field[@name='date_range_search_id']"):
            # Field was inserted explicitely
            return result
        separator = etree.Element("separator")
        field = etree.Element(
            "field",
            attrib={
                "name": "date_range_search_id",
                "string": _("Period"),
            }
        )
        groups = root.xpath("/search/group")
        if groups:
            groups[0].addprevious(separator)
            groups[0].addprevious(field)
        else:
            search = root.xpath("/search")
            search[0].append(separator)
            search[0].append(field)
        result['arch'] = etree.tostring(root, encoding='unicode')
        return result

    @api.model
    def load_views(self, views, options=None):
        """Adapt the label of the dummy search field

        Ensure the technical name does not show up in the Custom Filter
        fields list (while still showing up in the Export widget)
        """
        result = super().load_views(views, options=options)
        if "date_range_search_id" in result["fields"]:
            result["fields"]["date_range_search_id"]["string"] = _("Period")
        return result
