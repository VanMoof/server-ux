For regular usage, see `Usage` below. This section is to clarify optional
functionality to developers.

To configure a model to use the Many2one style search field, make the model
inherit from `date.range.search.mixin`:

.. code-block::

    class AccountMove(models.Model):
        _name = "account.move"
        _inherit = ["account.move", "date.range.search.mixin"]

This will make a `Period` field show up in the search view:

  .. figure:: https://raw.githubusercontent.com/OCA/server-tools/12.0/date_range/static/description/date_range_many2one_search_field.png
     :scale: 80 %
     :alt: Date range Many2one search field

By default, the mixin works on the `date` field. If you want the mixin to work
on a field with a different name, you can set a property on your model:

.. code-block::

   _date_range_search_field = "invoice_date"

By default, the field when read will contain a falsy value, but you can set
a code to specify if date ranges from a specific date range type should be
assigned:

.. code-block::

   _date_range_assign_type_code = "fiscal_years"

This should correspond with the code of a date range type that does not have
a company set.
