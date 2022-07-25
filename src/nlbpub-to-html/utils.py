import re
import hashlib


# calculate an MD5 of any object
def md5(obj, exclude=[], _path=[]):
    result = ""

    if isinstance(obj, dict):
        keys = obj.keys()
        sorted_keys = sorted([key for key in keys if key is not None])
        for key in sorted_keys:
            path = _path + [key]
            if not md5_exclude(path, exclude):
                result += md5(key, exclude=exclude, _path=path)
                result += md5(obj[key], exclude=exclude, _path=path)
        if None in keys:
            path = _path + ["*"]
            if not md5_exclude(path, exclude):
                result += md5(None, exclude=exclude, _path=path)
                result += md5(obj[None], exclude=exclude, _path=path)

    elif isinstance(obj, list):
        for position, item in enumerate(obj):
            path = _path + [str(position)]
            if not md5_exclude(path, exclude):
                result += md5(item, exclude=exclude, _path=path)

    else:
        result += str(type(obj)) + str(obj)

    return hashlib.md5(result.encode('utf-8')).hexdigest()


def md5_exclude(path, exclude):
    if not exclude:
        return False

    pathstring = ".".join(path)

    for ex in exclude:
        e = ex.replace("*", "[^\\.]*")  # replace * with [^\.]* so that we can treat it as a regex

        if re.match(e, pathstring):
            # this field should be excluded
            return True

    return False
