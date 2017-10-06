# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import sys, os
import shippo, yaml
from pathlib import Path
from whaaaaat import prompt, print_json
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

MAX_TRANSIT_TIME_DAYS = 7

def prompt_to_continue(aMessage):
  answers = prompt([
    {'type': 'confirm', 'name': 'continue', 'message': aMessage},
  ])
  if not answers['continue']:
    sys.exit(0)

def display_url(aUrl):
  import subprocess
  subprocess.call(['open', aUrl])

def display_messages(aMessages, prompt="Are these alerts okay?", onProblem=None):
  if len(aMessages) > 0:
    if onProblem:
        onProblem()
    for m in aMessages:
      print("Alert: [{source}] {text} (Code={code})".format(**m))
    prompt_to_continue(prompt)

def choose_rate_for_shipment(aShipmentObj):
    # Rates are stored in the `rates` array
    # The details on the returned object are here: https://goshippo.com/docs/reference#rates
    choices=[]

    for rateObj in sorted(aShipmentObj.rates, key=lambda r: float(r.amount)):
        shortDesc="{provider} {servicelevel[name]} ({estimated_days} days)".format(**rateObj)
        desc = "{provider} {servicelevel[name]} for {currency} {amount} with est. transit time of {estimated_days} days".format(**rateObj)
        for a in rateObj.attributes:
            desc += " [{}]".format(a)
        choices.append({'name': desc, 'value': rateObj, 'short': shortDesc})

    questions = [
      {'type': 'list', 'name': 'service', 'message': "What service do you want?", 'choices': choices}
    ]
    return prompt(questions)['service']

def finish_and_offer_to_print_transaction(aTransaction):
  # print label_url and tracking_number
  if aTransaction.status == "SUCCESS":
    print("Purchased label with tracking number {}".format(aTransaction.tracking_number))
    print("The label can be downloaded at {}".format(aTransaction.label_url))

    display_url(aTransaction.label_url)
  else:
    print("Failed purchasing the label due to:")
    display_messages(aTransaction.messages, prompt="Failed to create the label")

##
## Main logic
##

conf_file = os.path.join(Path.home(), ".shippo_it.yaml")

address_from = None
# Load config file
with open(conf_file, "r") as conf_stream:
  config_data = yaml.load(conf_stream)

  # Determine the available API keys
  api_keys = []
  try:
    for key, value in config_data["api_key"].items():
      api_keys.append({'name': key, 'value': value })
  except KeyError:
    print("The config file [{}] does not contain a dictionary of API keys under the heading of 'api_key'".format(conf_file))
    print("")
    sys.exit(1)

  # Choose API key
  questions = [
    {'type': 'list', 'name': 'apikey', 'message': "Which API key should we use?", 'choices': api_keys}
  ]
  shippo.api_key = prompt(questions)['apikey']

  # Set up sender address
  try:
    config_data['from']['validate'] = True
    address_from = shippo.Address.create(**config_data['from'])
    display_messages(address_from.validation_results.messages, "Are these sender address problems OK?")
  except:
    print("The config file [{}] does not contain the sender's address under the heading of 'from'".format(conf_file))
    print("You need to make sure to have the right fields. The website at")
    print("https://goshippo.com/docs/reference#addresses has a list of those fields." )
    print("")
    sys.exit(1)

## Load parcel configuration
print("Parcel information")

parcel_choices = []
parcel_list = os.path.join(sys.path[0], 'parcel_templates.yaml')
with open(parcel_list, "r") as parcel_stream:
  parcel_data = yaml.load(parcel_stream)

  for key, value in parcel_data.items():
    name = "[{template}] Unit={v[u]} L={v[l]} W={v[w]} H={v[h]}".format(template=key, v=value)
    if value['template']:
      value['template_name'] = key
    parcel_choices.append({'name': name, 'value': value})


parcel_questions = []
parcel_template_answers = prompt([
    {'type': 'confirm', 'name': 'template', 'message': "Use a parcel template?"},
])
if parcel_template_answers['template']:
  # Select from the template list
  parcel_questions.append({'type': 'list',
      'name': 'template',
      'message': "What parcel template should we use?",
      'choices': parcel_choices})
else:
  # Custom questions
  parcel_questions.append({'type': 'input', 'name': 'length', 'message': "Length?"})
  parcel_questions.append({'type': 'input', 'name': 'width', 'message': "Width?"})
  parcel_questions.append({'type': 'input', 'name': 'height', 'message': "Height?"})
  parcel_questions.append({'type': 'list', 'name': 'distance_unit',
    'message': "Parcel distance units?", 'choices': ["cm", "in"]})

# Standard questions
parcel_questions.append({'type': 'input', 'name': 'mass', 'message': "Parcel mass?"})
parcel_questions.append({'type': 'list', 'name': 'mass_unit',
    'message': "Parcel mass units?", 'choices': ["oz", "lb", "kg"]})

parcel_response = prompt(parcel_questions)

# If they chose a template
if "template" in parcel_response:
    parcel_response["length"] = parcel_response['template']['l']
    parcel_response["width"] = parcel_response['template']['w']
    parcel_response["height"] = parcel_response['template']['h']
    parcel_response["distance_unit"] = parcel_response['template']['u']
    parcel_response["template_name"] = parcel_response['template']['template_name']
else:
    parcel_response["template_name"] = None

parcel = {
    "length": parcel_response['length'],
    "width": parcel_response['width'],
    "height": parcel_response['height'],
    "distance_unit": parcel_response['distance_unit'],
    "template": parcel_response['template_name'],
    "weight": parcel_response['mass'],
    "mass_unit": parcel_response['mass_unit']
}

# Get recipient
print("Recipient information")
address_questions = [
  {'type': 'input', 'name': 'name', 'message': "Name" },
  {'type': 'input', 'name': 'street1', 'message': "Street Address" },
  {'type': 'input', 'name': 'street2', 'message': "Street (line 2)" },
  {'type': 'input', 'name': 'city', 'message': "City" },
  {'type': 'input', 'name': 'state', 'message': "State",
    'validate': lambda s: len(s)==2 or "2 letter abbreviations" },
  {'type': 'input', 'name': 'zip', 'message': "ZIP" },
  {'type': 'input', 'name': 'country', 'message': "Country Code" },
  {'type': 'input', 'name': 'company', 'message': "Company" },
  {'type': 'input', 'name': 'phone', 'message': "Phone" },
  {'type': 'input', 'name': 'email', 'message': "E-Mail" },
]
address_response = prompt(address_questions)

address_to = shippo.Address.create(**address_response, validate=True)
display_messages(address_to.validation_results.messages, "Are these address problems OK?",
     onProblem=lambda: print_json(address_to))

if not address_to.validation_results.is_valid:
  prompt_to_continue("The validator thinks this destination address is invalid. Continue anyway?")

customs_declaration=None

# customs_item = {
#     "description":"T-Shirt",
#     "quantity":20,
#     "net_weight":"1",
#     "mass_unit":"lb",
#     "value_amount":"200",
#     "value_currency":"USD",
#     "origin_country":"US",
#     "tariff_number":"",
# }

# customs_declaration = shippo.CustomsDeclaration.create(
#     contents_type= 'MERCHANDISE',
#     contents_explanation= 'T-Shirt purchase',
#     non_delivery_option= 'RETURN',
#     certify= True,
#     certify_signer= 'Person Name',
#     items= [customs_item]
# )

print("Destination Address:")
print_json(address_to);
print("Parcel:")
print_json(parcel)
if customs_declaration:
    print("Customs declaration:")
    print_json(customs_declaration)

prompt_to_continue("Does this look acceptable?")

# Creating the shipment object. async=False indicates that the function will wait until all
# rates are generated before it returns.
# The reference for the shipment object is here: https://goshippo.com/docs/reference#shipments
# By default Shippo API operates on an async basis. You can read about our async flow here: https://goshippo.com/docs/async
shipment = shippo.Shipment.create(
    address_from=address_from,
    address_to=address_to,
    parcels=[parcel],
    # customs_declaration=customs_declaration,
    async=False
)

display_messages(shipment.messages, prompt="Are these shipment alerts OK?")

rate = choose_rate_for_shipment(shipment)
print("Picked service {} {} for {} {} with est. transit time of {} days".format(rate['provider'],
    rate['servicelevel']['name'], rate['currency'], rate['amount'], rate['estimated_days']));

print_json(rate)
prompt_to_continue("Ready to purchase this rate?")

# Purchase the desired rate. async=False indicates that the function will wait until the
# carrier returns a shipping label before it returns
transaction = shippo.Transaction.create(rate=rate.object_id, async=False)
print_json(transaction)

finish_and_offer_to_print_transaction(transaction)

prompt_to_continue("Would you like a return label?")

shipment_return = shippo.Shipment.create(
    address_from = address_from,
    address_to = address_to,
    parcels = [parcel],
    extra = {'is_return': True},
    async = False
)

return_rate = choose_rate_for_shipment(shipment_return)
print("Picked return service {} {} for {} {} with est. transit time of {} days".format(rate['provider'],
    rate['servicelevel']['name'], rate['currency'], rate['amount'], rate['estimated_days']));

return_transaction = shippo.Transaction.create(rate=return_rate.object_id, async=False)

finish_and_offer_to_print_transaction(return_transaction)
