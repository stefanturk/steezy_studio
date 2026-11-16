"""Where a tester's feedback goes. Empty URL = the Send feedback button stays hidden.

URL is the Apps Script web app's /exec address (see feedback/apps_script.gs). TOKEN only
filters out bots that stumble on the address; it is not a secret and can't be one in a
public app. Change it in both places if it ever gets abused.
"""
URL = "https://script.google.com/macros/s/AKfycbz7CmvZw-UVk0F08N4y5hED7Z-rZOV4xuPJFlAK5P9d611TQqMKgSIDfv_FL30vpIra/exec"
TOKEN = "steezy-feedback-v1"
