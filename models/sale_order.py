# -*- encoding: utf-8 -*-
##############################################################################

from odoo import models, fields, api

#action_confirm


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self):
        ctx = dict(self.env.context) or {}
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        if ctx.get('pre_payment', False):
            res['quantity'] = self.product_uom_qty
        return res
