from odoo import fields, models


class TestDateRangeSearchMixin(models.Model):
    _name = "test.date.range.search.mixin"
    _inherit = ["date.range.search.mixin"]
    _date_range_search_field = "test_date"
    _date_range_assign_type_code = 'test_code'

    name = fields.Char()
    test_date = fields.Date()
