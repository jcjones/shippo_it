# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import sys, os, webbrowser
import shippo, yaml
from pathlib import Path
from whaaaaat import prompt, print_json
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

assert sys.version_info >= (3,2)

def print_clean_json(aObj):
  print_json({k: v for k, v in aObj.items() if v is not "" and not None})

def prompt_to_continue(aMessage):
  """
  Return True if the user wants to continue
  """
  answers = prompt([
    {'type': 'confirm', 'name': 'continue', 'message': aMessage},
  ])
  return answers['continue']

def display_messages(aMessages, prompt="Are these alerts okay?", onProblem=None):
  """
  Return True if the user wants to continue
  """
  if len(aMessages) > 0:
    if onProblem:
        onProblem()
    for m in aMessages:
      print("Alert: [{source}] {text} (Code={code})".format(**m))
    return prompt_to_continue(prompt)

  return True

def format_address(aAddress):
  return "{name}, {company}, {city}, {country}".format(**aAddress)

def format_parcel(aParcel):
  return "[{template}] {length}{distance_unit} x {width}{distance_unit} x {height}{distance_unit}, {weight}{mass_unit}".format(**aParcel)

def find_existing_address(aAddress):
  all_addresses = shippo.Address.all()
  for addr in all_addresses['results']:
    for x in ['city', 'country', 'company', 'state', 'street1', 'zip', 'name']:
      if addr[x] != aAddress[x]:
        continue
    return aAddress
  return None

def prompt_for_address(priorAddress={}):
  address_questions = [
    {'type': 'input', 'name': 'name', 'message': "Name" },
    {'type': 'input', 'name': 'street1', 'message': "Street Address" },
    {'type': 'input', 'name': 'street2', 'message': "Street (line 2)" },
    {'type': 'input', 'name': 'street3', 'message': "Street (line 3)" },
    {'type': 'input', 'name': 'city', 'message': "City",
      'validate': lambda s: len(s)>=2 or "City must be at least 2 letters" },
    {'type': 'input', 'name': 'state', 'message': "State" },
    {'type': 'input', 'name': 'zip', 'message': "Postal Code" },
    {'type': 'input', 'name': 'country', 'message': "Country Code (2-letter ISO)",
      'validate': lambda s: len(s)==2 or "Country code must be 2 letters (ISO)" },
    {'type': 'input', 'name': 'company', 'message': "Company" },
    {'type': 'input', 'name': 'phone', 'message': "Phone" },
    {'type': 'input', 'name': 'email', 'message': "E-Mail" },
  ]

  # Fill in defaults, if any
  if priorAddress is not None:
    for q in address_questions:
      if q['name'] in priorAddress:
        q['default'] = priorAddress[q['name']]

  address_response = prompt(address_questions)
  return shippo.Address.create(**address_response, validate=True)


def prompt_for_customs_items(priorItems=[]):
  # Only support one item at a time for now

  print("Parcel Item #1")

  customs_questions = [
    {'type': 'input', 'name': 'description', 'message': "Item description" },
    {'type': 'input', 'name': 'quantity', 'message': "Item quantity",
     'validate': lambda s: float(s).is_integer() or "Must be an integer quantity" },
    {'type': 'input', 'name': 'net_weight', 'message': "Item mass?",
     'validate': lambda s: s.replace('.','',1).isdigit() or "Must be a numberical quantity"},
    {'type': 'list', 'name': 'mass_unit', 'message': "Parcel mass units?",
     'choices': ["oz", "lb", "kg"]},
    {'type': 'input', 'name': 'value_amount', 'message': "Item value?",
     'validate': lambda s: s.replace('.','',1).isdigit() or "Must be a numberical quantity"},
    {'type': 'input', 'name': 'value_currency', 'message': "Item value currency (3 letter code)?",
     'validate': lambda s: len(s)==3 or "Currency code must be 3 letter" },
    {'type': 'input', 'name': 'origin_country', 'message': "Item origin Country Code (2-letter ISO)",
      'validate': lambda s: len(s)==2 or "Country code must be 2 letters" },
    {'type': 'input', 'name': 'tariff_number', 'message': "Item tariff number, or blank" },
    {'type': 'input', 'name': 'sku_code', 'message': "Item SKU, or blank" },
  ]

  # Fill in defaults, if any
  # for q in customs_questions:
  #   if q['name'] in priorItems[0]:
  #     q['default'] = priorCustoms[q['name']]

  customs_response = prompt(customs_questions)
  return [customs_response]

def prompt_for_customs(priorCustoms={}):
  items = []
  if 'items' in priorCustoms:
    items = priorCustoms['items']
  items = prompt_for_customs_items(items)

  print_json(items)

  customs_questions = [
    {'type': 'list', 'name': 'contents_type', 'message': "Type",
      'choices': ["DOCUMENTS", "GIFT", "SAMPLE", "MERCHANDISE", "HUMANITARIAN_DONATION",
                  "RETURN_MERCHANDISE", "OTHER"] },
    {'type': 'input', 'name': 'contents_explanation', 'message': "Explanation of Contents (required if OTHER)" },
    {'type': 'list', 'name': 'non_delivery_option', 'message': "In the event of non-delivery?",
        'choices': ["ABANDON", "RETURN"] },
    {'type': 'confirm', 'name': 'certify', 'message': "Do you Certify this as true?" },
    {'type': 'input', 'name': 'certify_signer', 'message': "Name of certifier" },
  ]

  # Fill in defaults, if any
  for q in customs_questions:
    if q['name'] in priorCustoms:
      q['default'] = priorCustoms[q['name']]

  customs_response = prompt(customs_questions)
  customs_response['items'] = items

  print_clean_json(customs_response)
  return shippo.CustomsDeclaration.create(**customs_response)

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

    if len(choices) == 0:
      raise Exception("There are no rates available.")

    questions = [
      {'type': 'list', 'name': 'service', 'message': "What service do you want?", 'choices': choices}
    ]
    return prompt(questions)['service']

def finish_and_offer_to_print_transaction(aTransaction):
  # print label_url and tracking_number
  if aTransaction.status == "SUCCESS":
    print("Purchased label with tracking number {}".format(aTransaction.tracking_number))
    print("The label can be downloaded at {}".format(aTransaction.label_url))

    webbrowser.open(aTransaction.label_url)
  else:
    print("Failed purchasing the label due to:")
    if not display_messages(aTransaction.messages, prompt="Failed to create the label"):
      sys.exit(0)

def get_parcel_information():
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

  return {
      "length": parcel_response['length'],
      "width": parcel_response['width'],
      "height": parcel_response['height'],
      "distance_unit": parcel_response['distance_unit'],
      "template": parcel_response['template_name'],
      "weight": parcel_response['mass'],
      "mass_unit": parcel_response['mass_unit']
  }

def get_address(noun="Addressee", choices_text="Choose an addressee", exclude_addr=None):
  print("{} information".format(noun))
  if prompt_to_continue("Choose an existing {}?".format(noun)):
    choices = {}

    all_addresses = shippo.Address.all()
    for addr in all_addresses['results']:
      if exclude_addr is not None and format_address(addr) == format_address(exclude_addr):
        continue
      choices[format_address(addr)] = {'name': format_address(addr),
                                       'value': addr}
    result = prompt({'type': 'list', 'name': 'chosen_address',
                     'message': choices_text, 'choices': choices.values()})

    return result['chosen_address']

  # Otherwise, let's prompt and enter a loop.
  address = None
  keepGoing = False
  while address is None or keepGoing:
    address = prompt_for_address(priorAddress=address)

    if 'is_valid' not in address.validation_results:
      if not prompt_to_continue("Could not validate address. Is that OK?"):
        keepGoing = True
        continue

    if not address.validation_results['is_valid']:
      if display_messages(address.validation_results.messages,
          "The validator thinks this {} address is invalid. Retry? (No will abort)".format(noun),
           onProblem=lambda: print_clean_json(address)):
        keepGoing = True
        continue
      else:
        sys.exit(0)

    if len(address.validation_results.messages) > 0:
      if not display_messages(address.validation_results.messages, "Are these address problems OK?",
                              onProblem=lambda: print_clean_json(address)):
        keepGoing = True

  print("Stored {} address for {}:".format(noun, format_address(address)))
  print_clean_json(address)
  return address

##
## Action logic
##

def ship_item(address_from=None, address_to=None, customs_declaration=None):
  while address_from is None:
    address_from = get_address(noun="Sender", choices_text="Prior senders", exclude_addr=address_to)

  # Get recipient
  while address_to is None:
    address_to = get_address(noun="Recipient", choices_text="Prior recipients", exclude_addr=address_from)

  # Get international information... if needed
  if address_to['country'] != address_from['country'] and prompt_to_continue(
                "Does this parcel need an international customs declaration?"):
    customs_declaration = prompt_for_customs()
    print("Customs declaration:")
    print_json(customs_declaration)

  ## Load parcel configuration
  print("Parcel information")
  parcel = get_parcel_information()

  print("Parcel: " + format_parcel(parcel))

  if not prompt_to_continue("Does this parcel look acceptable?"):
    return False

  # Creating the shipment object. async=False indicates that the function will wait until all
  # rates are generated before it returns.
  # The reference for the shipment object is here: https://goshippo.com/docs/reference#shipments
  # By default Shippo API operates on an async basis. You can read about our async flow here: https://goshippo.com/docs/async
  shipment = shippo.Shipment.create(
      address_from=address_from,
      address_to=address_to,
      parcels=[parcel],
      customs_declaration=customs_declaration,
      async=False
  )

  if not display_messages(shipment.messages, prompt="Are these shipment alerts OK?"):
    return False

  rate = choose_rate_for_shipment(shipment)
  print("Picked service {} {} for {} {} with est. transit time of {} days".format(rate['provider'],
      rate['servicelevel']['name'], rate['currency'], rate['amount'], rate['estimated_days']));

  print_json(rate)
  if not prompt_to_continue("Ready to purchase this rate?"):
    return False

  # Purchase the desired rate. async=False indicates that the function will wait until the
  # carrier returns a shipping label before it returns
  transaction = shippo.Transaction.create(rate=rate.object_id, async=False)
  print_json(transaction)

  finish_and_offer_to_print_transaction(transaction)

  if not prompt_to_continue("Would you like a return label?"):
    return True

  shipment_return = shippo.Shipment.create(
      address_from = address_from,
      address_to = address_to,
      parcels = [parcel],
      customs_declaration=customs_declaration,
      extra = {'is_return': True},
      async = False
  )

  return_rate = choose_rate_for_shipment(shipment_return)
  print("Picked return service {} {} for {} {} with est. transit time of {} days".format(rate['provider'],
      rate['servicelevel']['name'], rate['currency'], rate['amount'], rate['estimated_days']));

  return_transaction = shippo.Transaction.create(rate=return_rate.object_id, async=False)

  finish_and_offer_to_print_transaction(return_transaction)
  return True

def list_outgoing_items():
  all_transactions = shippo.Transaction.all()
  for tx in all_transactions['results']:
    if tx['object_state'] != "VALID":
      continue

    parcel = shippo.Parcel.retrieve(tx['parcel'])
    rate = shippo.Rate.retrieve(tx['rate'])
    shipment = shippo.Shipment.retrieve(rate['shipment'])

    print(shipment['shipment_date'] + " To: " + format_address(shipment['address_to']) + " " + tx['status'])

    print("Tracking number: {tracking_number}".format(**tx))
    if tx['tracking_status'] != "UNKNOWN":
      print("Status: {tracking_status} ETA: {eta}".format(**tx))
      print("{tracking_url_provider}".format(**tx))
    print("Parcel: " + format_parcel(parcel))
    print("{provider} {servicelevel[name]}: {amount} {currency} (est. {estimated_days} days)".format(**rate))

    if shipment['customs_declaration']:
      customs = shippo.CustomsDeclaration.retrieve(shipment['customs_declaration'])
      print_json(customs)
      for itemId in customs['items']:
        item = shippo.CustomsItem.retrieve(itemId)
        print_json(item)

    if len(tx['messages']) > 0:
      print_json(tx['messages'])
    print("")

  return True

##
## Main logic
##

conf_file = os.path.join(Path.home(), ".shippo_it.yaml")

address_home = None
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
    # Try to re-use old address
    address_home = find_existing_address(config_data['from'])
    if address_home is None:
      # Create it
      config_data['from']['validate'] = True
      address_home = shippo.Address.create(**config_data['from'])
      if not display_messages(address_home.validation_results.messages, "Are these sender address problems OK?"):
        sys.exit(0)
  except:
    print("The config file [{}] does not contain the sender's address under the heading of 'from'".format(conf_file))
    print("You need to make sure to have the right fields. The website at")
    print("https://goshippo.com/docs/reference#addresses has a list of those fields." )
    print("")
    sys.exit(1)


action_question = {'type': 'list', 'name': 'action', 'message': "What do you want to do?",
                   'choices': [{'value': 'ship', 'name': 'Ship a package'},
                               {'value': 'return', 'name': 'Produce a return label'},
                               {'value': 'list_outgoing', 'name': 'List sent packages'}]}
try:
  action = prompt([action_question])['action']
  if action == "ship":
    ship_item(address_from=address_home)
  if action == "return":
    ship_item(address_to=address_home)
  elif action == "list_outgoing":
    list_outgoing_items()
  else:
    raise Exception("Unexpected action: " + action)
except KeyError:
  pass
except EOFError:
  pass
