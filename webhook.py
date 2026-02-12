#!/usr/bin/env python3
import argparse
import yaml
from flask import Flask, request, jsonify, make_response
from github_auth import GithubAuth


def get_args():
    parser = argparse.ArgumentParser(
        description='Github Webhook proxy for Jenkins'
    )

    parser.add_argument(
        '-p', '--port',
        help='Port to listen on',
        type=int,
        default=8090
    )

    parser.add_argument(
        '-H', '--host',
        help='Host to bind to',
        default='0.0.0.0'
    )

    return parser.parse_args()


def load_config():
    try:
        with open('config.yml', 'r') as stream:
            return yaml.safe_load(stream)
    except FileNotFoundError:
        return None


def validate_config(config):
    if 'github' in config and 'required' in config['github']:
        required = config['github']['required']
        if 'email' in required and 'domain_required_as_primary' in required['email']:
            if 'domain' not in required['email']:
                raise KeyError('Configuration requires a specific domain name as a ' +
                               'primary email, but no domain was provided')


def validate_org(orgs, required_org):
    for org in orgs:
        if org['login'] == required_org:
            return True
    return False


def validate_email_domain(email_list, required_domain):
    for email_item in email_list:
        email_address = email_item['email']
        email_domain = email_address.split('@')[-1]
        if email_domain in required_domain:
            return {
                'email': email_address,
                'domain': email_domain,
                'primary': email_item['primary']
            }
    return None


def validate_primary_email(email_list, required_email_domain):
    for email_item in email_list:
        email_address = email_item['email']
        email_domain = email_address.split('@')[-1]
        if email_domain in required_email_domain:
            return True
    return False


def validate_auth_requirements(config, username, orgs, emails):
    if config \
            and 'github' in config \
            and 'required' in config['github']:
        required = config['github']['required']

    if 'org' in required:
        required_org = required['org']
        if not validate_org(orgs, required_org):
            raise PermissionError(f'User {username} is not a member of {required_org} Github organization')

    if 'email' in required and 'domain' in required['email']:
        domain = required['email']['domain']
        validated_email = validate_email_domain(emails, domain)
        if not validated_email:
            raise PermissionError(f'User {username} does not have a @{domain} email ' +
                                  'address associated with their Github account')

        if 'email' in required and 'domain_required_as_primary' in required['email']:
            domain = required['email']['domain']
            if not validate_primary_email(emails, domain):
                raise PermissionError(f'User {username} does not have an @{domain} address ' +
                                      'associated with their Github account')


def get_username(login):
    if 'spinnaker' in config \
            and 'username_mapping' in config['spinnaker'] \
            and login in config['spinnaker']['username_mapping']:
        return config['spinnaker']['username_mapping'][login]
    else:
        return login


app = Flask(__name__)
config = load_config()

if config:
    validate_config(config)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify(
        {
            'status': 'error',
            'msg': f'{request.url} not found',
            'detail': str(error)
        }
    ), 404)


@app.errorhandler(500)
def internal_server_error(error):
    return make_response(jsonify(
        {
            'status': 'error',
            'msg': 'Internal Server Error',
            'detail': str(error)
        }
    ), 500)


@app.route('/')
def ping():
    return make_response(jsonify(
        {
            'status': 'ok'
        }
    ), 200)


@app.route('/info', methods=['GET'])
def webhook_handler():
    try:
        headers = request.headers

        if 'Authorization' not in headers:
            make_response(jsonify(
                {
                    'status': 'error',
                    'msg': 'Authorization header not found in request'
                }
            ), 401)

        auth_header = headers.get('Authorization')

        if not auth_header:
            make_response(jsonify(
                {
                    'status': 'error',
                    'msg': 'Authorization header not present or empty'
                }
            ), 401)

        auth = auth_header.split(' ')
        access_token = auth[-1]
        github = GithubAuth(access_token)
        github.validate_scopes()
        info = github.get_user_info()
        orgs = github.get_org_list()
        emails = github.get_email_addresses()
        teams = github.get_user_teams(config)
        validate_auth_requirements(config, info['login'], orgs, emails)
        name_info = info['name'].split(' ')
        primary_email = ''
        org_memberships = ''
        org_list = []

        for email in emails:
            if email['primary']:
                primary_email = email['email']

        for org in orgs:
            org_list.append(org['login'])

        if len(org_list):
            org_memberships = ','.join(org_list)

        info['username'] = get_username(info['login'])
        info['firstname'] = name_info[0]
        info['lastname'] = name_info[-1]
        info['email'] = primary_email
        info['roles'] = teams

        # You could use a regex to check this, but it can possibly match
        # orgs with similar names instead of doing exact matching
        info['orgs'] = org_memberships

        # This should actually be checked by Gate but is not
        info['organizations_url'] = 'https://api.github.com/user/orgs'

        return make_response(jsonify(info), 200)
    except PermissionError as e:
        return make_response(jsonify(
            {
                'status': 'error',
                'msg': 'Unauthorized',
                'detail': str(e)
            }
        ), 401)


if __name__ == '__main__':
    args = get_args()
    app.run(host=args.host, port=args.port)
