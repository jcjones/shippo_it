# Shippo.It

A tool to interact with [Shippo](https://goshippo.com) via Python at the CLI

Requires:
- Python 3.4
- [shippo](https://github.com/goshippo/shippo-python-client/)
- [whaaaaat](https://github.com/finklabs/whaaaaat)
- [PyYAML](http://pyyaml.org/wiki/PyYAMLDocumentation)

## Example Usage

![Example usage](shippo-example.gif)

## Installation

```
git clone https://github.com/jcjones/shippo_it.git
pip3 install -r shippo_it/requirements.txt

cat >~/.shippo_it.yaml <<EOF
api_key:
 Test API: shippo_test_something_something
 Production API: shippo_live_something_something

from:
  name: A Person
  street1: 987 Main Street
  street2: Suite 123
  company: A Shipping Company
  phone: +44 1234 56789
  city: Gotham
  state: Happy
  zip: ALL HAIL
  country: GB
EOF

python3 shippo_it/shippo_it.py
```

## Bugs?

Feel free to file an issue, but I'm not planning to really maintain this. You're
probably better off forking it and fixing it yourself. Sorry in advance!
