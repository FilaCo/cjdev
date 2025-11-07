GITCODE_API_URL='https://api.gitcode.com/api/v5'

# $1 - owner
# $2 - repo
# $3 - title
# $4 - head
# $5 - base
gitcode::pr::create() {
  curl --location --request POST "$GITCODE_API_URL/repos/$1/$2/pulls?access_token=$GITCODE_API_TOKEN" \
    --header 'Content-Type: application/json' \
    --data-raw "{
      \"title\": \"$3\",
      \"head\": \"$4\"
      \"base\": \"$5\"
    }"
}
