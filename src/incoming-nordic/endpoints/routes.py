import logging
import os

import requests
import server

def return_response(response):
    try:
        logging.info(response.json)
        response_json = server.jsonify(response.json, response.status_code)
        response_json.headers.set(response.headers.items())
        return response_json
    except:
        logging.info(response.text)
        return response.text, response.status_code, response.headers.items()

@server.route(server.root_path, methods=["GET"], require_auth=None)
def root_path():
    response = requests.get(os.environ.get("PRODSYS_API_URL"))
    return return_response(response)

@server.route(server.root_path + '/editions/<string:editionId>', methods=["POST"], require_auth=None)
def proxy(editionId):
    # Trigger incoming-nordic pipeline
    # TODO Change to use this image instead of old production system when ready
    response = requests.post(os.environ.get("NLB_API_URL")+f"/v1/production/steps/incoming-nordic/editions/{editionId}/trigger")
    return return_response(response)
