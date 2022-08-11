import logging
import os

import requests
import core.server

from incoming_nordic import IncomingNordic

def return_response(response):
    try:
        logging.info(response.json)
        response_json = core.server.jsonify(response.json, response.status_code)
        response_json.headers.set(response.headers.items())
        return response_json
    except:
        logging.info(response.text)
        return response.text, response.status_code, response.headers.items()


@core.server.route(core.server.root_path, methods=["GET"], require_auth=None)
def root_path():
    response = requests.get(os.environ.get("PRODSYS_API_URL"))
    return return_response(response)


@core.server.route(core.server.root_path + '/editions/<string:editionId>', methods=["POST"], require_auth=None)
def process_edition(editionId):
    # Create new IncomingNordic object
    process = IncomingNordic(editionId=editionId)

    # Return the report
    return return_response({ "success": process.run()})
