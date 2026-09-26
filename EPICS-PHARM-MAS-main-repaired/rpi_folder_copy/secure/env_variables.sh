#!/bin/sh
# Template only. A deployed key from the old snapshot must be rotated.
: "${MAS_API_KEY:?Set MAS_API_KEY outside source control before starting the API}"
export MAS_API_KEY
