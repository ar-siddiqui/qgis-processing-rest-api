import logging
import os
import sys
from datetime import datetime
from io import StringIO

import html2text
from pytz import timezone
from qgis.core import QgsApplication
from werkzeug.exceptions import BadRequest

# Append the path where processing plugin can be found
sys.path.append("/usr/share/qgis/python/plugins")

import processing
from processing.core.Processing import Processing

from utils import Logger

## Init QGIS Processing
# See https://gis.stackexchange.com/a/155852/4972 for details about the prefix
QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], False)
qgs.initQgis()

## Add third party plugins
Processing.initialize()
try:
    from curve_number_generator.processing.curve_number_generator_provider import CurveNumberGeneratorProvider

    provider = CurveNumberGeneratorProvider()
    QgsApplication.processingRegistry().addProvider(provider)
except Exception as e:
    logging.error(str(e))


def list_algorithms():
    algorithms = []
    for alg in QgsApplication.processingRegistry().algorithms():
        algorithms.append(
            {
                "provider_id": alg.id().partition(":")[0],
                "algorithm_id": alg.id().partition(":")[-1],
                "algorith_name": alg.displayName(),
            }
        )
    return algorithms


all_algs = list_algorithms()
providers_ids = {alg["provider_id"] for alg in all_algs}
alg_ids = {alg["algorithm_id"] for alg in all_algs}


def get_alg_help(provider_id, algorithm_id):
    verify_alg_ids(provider_id, algorithm_id)

    save_stdout = sys.stdout
    result = StringIO()
    sys.stdout = result
    str(processing.algorithmHelp(f"{provider_id}:{algorithm_id}"))
    sys.stdout = save_stdout
    h = html2text.HTML2Text()
    content = result.getvalue()
    content = content.replace("</html>", "<html>")
    content = content.split("<html>")
    # because of QGIS return str format we know the str would not start and end with html
    if len(content) > 1:
        content = content[0] + h.handle("\n".join(content[1:-1])) + content[-1]
    else:
        content = content[0]
    return content


def process_alg(provider_id, algorithm_id, data):
    verify_alg_ids(provider_id, algorithm_id)
    data_str = str(data)
    if "TEMPORARY_OUTPUT" in data_str:
        raise BadRequest("'TEMPORARY_OUTPUT' is not allowed. Please provide a filepath for the output")

    date = datetime.now(timezone(os.environ["TIMEZONE"])).date().strftime("%Y_%m_%d")
    time_now = datetime.now(timezone(os.environ["TIMEZONE"])).time().strftime("%H_%M_%S")
    log_file = f"{date}_{time_now}_{provider_id}_{algorithm_id}.log"
    feedback = Logger(log_file)

    result = processing.run(f"{provider_id}:{algorithm_id}", data, feedback=feedback)
    return result


def verify_alg_ids(provider_id, algorithm_id):
    if not provider_id in providers_ids:
        raise BadRequest(f"'{provider_id}' is not a valid provider_id. Request valid ids using '/list'")
    if not algorithm_id in alg_ids:
        raise BadRequest(f"'{algorithm_id}' is not a valid algorithm_id. Request valid ids using '/list'")
