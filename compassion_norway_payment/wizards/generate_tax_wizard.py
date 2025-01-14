##############################################################################
#
#    Copyright (C) 2022 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty
#    @author: Robin Berguerand <robin.berguerand@gmail.com>
#
#    The licence is in the file __manifest__.py
#
##############################################################################
import base64
from odoo import api, models, fields
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom


class GenerateTaxWizard(models.Model):
    _inherit = "generate.tax.wizard"

    def generate_tax(self):
        company = self.env.company
        if company.country_id.name != "Norway":
            return super().generate_tax()
        ret = self.env['account.move'].read_group([
            ('company_id', '=', company.id),
            ('payment_state', '=', 'paid'),
            ('last_payment', '>=', datetime(int(self.year), 1, 1)),
            ('last_payment', '<=', datetime(int(self.year), 12, 31)),
            ('invoice_category', 'in', ['fund', 'sponsorship']),
        ], ['amount_total', 'last_payment'],
            groupby=['partner_id'], lazy=False)
        total_amount_year = {}
        for a in ret:
            if a['partner_id'][0] not in total_amount_year:
                total_amount_year[a['partner_id'][0]] = 0
            total_amount_year[a['partner_id'][0]] += a['amount_total']
        grouped_amounts = {a['partner_id'][0]: a['amount_total'] for a in ret if a['amount_total'] >= 500}

        def sub_with_txt(parent, tag, text, **extra):
            elem = ET.SubElement(parent, tag, extra)
            elem.text = text
            return elem

        def text_map(parent, data_map: dict):
            for key, value in data_map.items():
                sub_with_txt(parent, key, value)

        melding = ET.Element('melding')
        currently_connected = self.env.user.partner_id
        melding.attrib = {'xmlns': "urn:ske:fastsetting:innsamling:gavefrivilligorganisasjon:v2",
                          'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
                          ' xsi:schemaLocation': "urn:ske:fastsetting:innsamling:gavefrivilligorganisasjon:v2 "
                                                 "gavefrivilligorganisasjon_v2_0.xsd "

                          }

        leveranse = ET.SubElement(melding, 'leveranse')
        kildesystem = ET.SubElement(leveranse, 'kildesystem')
        kildesystem.text = "Kildesystemet v2.0.5"
        oppgavegiver = ET.SubElement(leveranse, 'oppgavegiver')
        text_map(oppgavegiver, {'organisasjonsnummer': company.vat, 'organisasjonsnavn': company.name})
        kontaktinformasjon = ET.SubElement(oppgavegiver, 'kontaktinformasjon')
        text_map(kontaktinformasjon,
                 {'navn': currently_connected.name, 'telefonnummer': currently_connected.phone,
                  'varselEpostadresse': currently_connected.email,
                  })
        text_map(leveranse, {'interektsaar': str(self.year),
                             'oppgavegiversLeveranseReferanse': f'REF{self.year}{datetime.now():%d%m%Y}',
                             'leveransetype': 'ordinaer'})
        total_amount = 0
        for partner_id, amount in grouped_amounts.items():
            partner = self.env['res.partner'].browse(partner_id)
            if partner.social_sec_nr:
                oppgave = ET.SubElement(leveranse, 'oppgave')
                oppgaveeier = ET.SubElement(oppgave, 'oppgaveeier')
                text_map(oppgaveeier, {'foedselsnummer': str(partner.social_sec_nr), 'navn': partner.name})
                text_map(oppgave, {'beloep': str(int(amount))})
                total_amount += amount
        oppgaveoppsummering = ET.SubElement(leveranse, 'oppgaveoppsummering')
        text_map(oppgaveoppsummering, {'antallOppgaver': str(len(grouped_amounts)),
                                       'sumBeloep': str(int(total_amount))})
        xmlstr = minidom.parseString(ET.tostring(melding)).toprettyxml(indent="   ", encoding='UTF-8')

        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        attachment_obj = self.env['ir.attachment']
        # create attachment
        data = base64.b64encode(str.encode(xmlstr, 'utf-8'))
        attachment_id = attachment_obj.create(
            [{'name': f"Tax_{self.year}_{company.name}.xml", 'datas': data}])
        # prepare download url
        download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
        # download
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "new",
        }
