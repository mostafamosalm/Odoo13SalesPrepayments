# -*- encoding: utf-8 -*-
##############################################################################

{
    'name': "Sale Pre-Payments",
    'version': "13.0.0.1",
    'author': "Niraj Pajwani",
    'category': "Sales",
    'summary': """Sale Order Pre Payments""",
    'description': """Sale Order Pre Payments""",
    'depends': ['account', 'sale_stock', 'sale_management'],
    'data': [
            'wizard/wizard_sale_order_pre_payment_view.xml',
            'views/sale_order_views.xml',
    ],
    'installable': True,
    'auto_install': False
}
