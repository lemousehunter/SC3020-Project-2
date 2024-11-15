import json
from flask.json.provider import DefaultJSONProvider


class SetEncoder(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)