#!/usr/bin/env python

import json

from app.bootstrap import reset_lab


if __name__ == "__main__":
    print(json.dumps(reset_lab(), indent=2, sort_keys=True))
