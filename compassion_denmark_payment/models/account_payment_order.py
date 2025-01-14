##############################################################################
#
#    Copyright (C) 2022 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty
#    @author: Robin Berguerand <robin.berguerand@gmail.com>
#
#    The licence is in the file __manifest__.py
#
##############################################################################

from lxml import etree

from odoo import _, exceptions, fields, models
from odoo.exceptions import UserError
from datetime import date
from .. import beservice


class AccountPaymentOrder(models.Model):
    _inherit = "account.payment.order"

    def format_transmission_number(self):
        return "{}1".format(self.create_date.strftime("%d%m%y"))

    def generate_payment_file(self):
        self.ensure_one()
        if self.payment_method_id.code != "denmark_direct_debit":
            return super().generate_payment_file()

        data_delivery = beservice.DataDeliveryCollection(
            data_supplier_number=self.payment_mode_id.initiating_party_scheme,
            subsystem='BS1',
            delivery_type=beservice.DeliveryType.COLLECTION_DATA, delivery_identification=1)

        data_delivery.add_section(data_supplier_id=self.payment_mode_id.initiating_party_identifier,
                                  pbs_number=self.payment_mode_id.initiating_party_issuer,
                                  debtor_group_number=1)

        for bank_line in self.bank_line_ids:
            text_lines = []
            for line in bank_line.payment_line_ids:
                for invoice_line in line.move_line_id.move_id.invoice_line_ids:
                    text_lines.append((invoice_line.product_id.id, f"{int(invoice_line.credit)}  {invoice_line.name}"))
            text_lines.sort(key=lambda a: a[0])

            data_delivery.sections[0].add_payment(customer_number=f'{bank_line.partner_id.ref:15}',
                                                  mandate_number=bank_line.payment_line_ids[0].move_line_id.move_id.
                                                  line_ids.mapped('contract_id').group_id.ref,
                                                  amount=bank_line.amount_currency,
                                                  sign_code=beservice.SignCode.COLLECTION,
                                                  payment_date=bank_line.date,
                                                  text_lines=text_lines
                                                  )
        return data_delivery.to_ocr().encode('iso-8859-1'), "{}.xml".format(self.name)
