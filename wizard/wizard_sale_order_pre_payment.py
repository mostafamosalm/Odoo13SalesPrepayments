# -*- encoding: utf-8 -*-
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero


class WizardSaleOrderPrePayment(models.TransientModel):
    _name = 'wizard.sale.order.pre_payment'
    _description = 'Sale Order PrePayment'

    @api.model
    def _default_currency_id(self):
        if self._context.get('active_model') == 'sale.order' and self._context.get('active_id', False):
            sale_order = self.env['sale.order'].browse(
                self._context.get('active_id'))
            return sale_order.currency_id

    @api.model
    def _default_payment_method_id(self):
        payment_method_id = self.env['account.payment.method'].search(
            [('payment_type', '=', 'inbound')], limit=1)
        return payment_method_id and payment_method_id.id or False

    @api.depends('order_id.invoice_ids')
    def _compute_amount(self):
        self.ensure_one()
        invoice_ids = invoice_ids = self.order_id.invoice_ids.filtered(
            lambda inv: inv.type == 'out_invoice' and inv.state == 'posted')
        self.amount_due = sum(invoice_ids.mapped(
            'amount_residual')) or self.order_id.amount_total

    journal_id = fields.Many2one('account.journal', string="Journal")
    order_id = fields.Many2one('sale.order', string="Order Ref.")
    payment_date = fields.Date(
        string="Payment Date", default=fields.Date.context_today)
    amount_pay = fields.Float(string="Amount")
    amount_total = fields.Float(string="Total Amount of Sale Order")
    origin = fields.Char(string="Source Document")
    currency_id = fields.Many2one(
        'res.currency', string='Currency', default=_default_currency_id)
    payment_method_id = fields.Many2one(
        'account.payment.method', string='Payment Method Type',
        default=_default_payment_method_id)
    amount_due = fields.Float(
        string="Amount Due", compute='_compute_amount', compute_sudo=True)
    communication = fields.Char('Memo')

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            payment_method_ids = self.journal_id.inbound_payment_method_ids
            if payment_method_ids:
                self.payment_method_id = payment_method_ids and payment_method_ids[0]

    @api.model
    def default_get(self, fields):
        ctx = dict(self.env.context) or {}
        res = super(WizardSaleOrderPrePayment, self).default_get(fields)
        if ctx.get('active_model', '') == 'sale.order':
            order_id = self.env[ctx['active_model']].browse(
                ctx.get('active_ids', []))
            res.update({'origin': order_id.name,
                        'order_id': order_id.id,
                        'amount_total': order_id.amount_total})
        return res

    def _prepare_payment_vals(self, invoice):
        '''Create the payment values.
        :return: The payment values as a dictionary.
        '''
        values = {
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_date': self.payment_date,
            'communication': self.origin,
            'invoice_ids': [(6, 0, invoice.ids)],
            'payment_type': 'inbound',
            'amount': self.amount_pay,
            'currency_id': invoice.currency_id.id,
            'partner_id': invoice.commercial_partner_id.id,
            'partner_type': 'customer',
            'partner_bank_account_id': invoice.invoice_partner_bank_id.id,
        }
        return values

    def action_process(self):
        self.ensure_one()
        if float_is_zero(self.amount_pay, precision_rounding=self.currency_id.rounding):
            return {'type': 'ir.actions.act_window_close'}

        if self.amount_pay < 0.00:
            raise ValidationError(_('Amount pay should be positive.'))

        if self.amount_pay > self.amount_due:
            raise ValidationError(_('You cannot pay more than due amount!'))

        invoice_ids = self.order_id.invoice_ids.filtered(
            lambda inv: inv.type == 'out_invoice')
        create_invoice = False

        if not invoice_ids or all(inv.state == 'cancel' for inv in invoice_ids):
            create_invoice = True

        move = self.env['account.move']
        if create_invoice:
            # Invoice values.
            invoice_vals = self.order_id._prepare_invoice()
            pending_section = None

            # Invoice line values.
            for line in self.order_id.order_line:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue
                if pending_section:
                    invoice_vals['invoice_line_ids'].append(
                        (0, 0, pending_section.with_context(
                            pre_payment=True)._prepare_invoice_line()))
                    pending_section = None
                invoice_vals['invoice_line_ids'].append(
                    (0, 0, line.with_context(
                        pre_payment=True)._prepare_invoice_line()))

            move |= self.env['account.move'].sudo().with_context(
                default_type='out_invoice').create(invoice_vals)

            if move:
                move.message_post_with_view(
                    'mail.message_origin_link',
                    values={'self': move, 'origin': move.line_ids.mapped(
                        'sale_line_ids.order_id')},
                    subtype_id=self.env.ref('mail.mt_note').id)
                move.action_post()
        else:
            move = invoice_ids.filtered(lambda inv: inv.state == 'posted')
        if move:
            payments = self.env['account.payment'].create(
                self._prepare_payment_vals(move))
            payments.post()
            payments.write({'communication': self.communication or ''})
            if move.invoice_payment_state == 'paid':
                self.order_id.action_confirm()
        return {'type': 'ir.actions.act_window_close'}
