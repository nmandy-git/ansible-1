#!/usr/bin/python

# Copyright 2019 Broadcom. All rights reserved.
# The term 'Broadcom' refers to Broadcom Inc. and/or its subsidiaries.
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'certified'}


DOCUMENTATION = '''

module: brocade_security_ipfilter_policy
short_description: Brocade security ipfilter policy Configuration
version_added: '2.7'
author: Broadcom BSN Ansible Team <Automation.BSN@broadcom.com>
description:
- Update security ipfilter policy configuration

options:

    credential:
        description:
        - login information including
          fos_ip_addr: ip address of the FOS switch
          fos_user_name: login name of FOS switch REST API
          fos_password: password of FOS switch REST API
          https: True for HTTPS, self for self-signed HTTPS, or False for HTTP
        type: dict
        required: true
    vfid:
        description:
        - vfid of the switch to target. The value can be -1 for
          FOS without VF enabled. For VF enabled FOS, a valid vfid
          should be given
        required: false
    throttle:
        description:
        - rest throttling delay in seconds.
        required: false
    ipfilter_policies:
        description:
        - list of ipfilter policies data structure
          All writable attributes supported
          by BSN REST API with - replaced with _.
        required: false
    active_policy:
        description:
        - name of the active policy. mutually exclusive
          with ipfilter_policies and delete_policy.
          This shoud come after policies are created and
          filled with rules
        required: false
    delete_policies:
        description:
        - name of the policy to be deleted. mutually exclusive
          with ipfilter_policies and active_policy.
        required: false

'''


EXAMPLES = """


  gather_facts: False

  vars:
    credential:
      fos_ip_addr: "{{fos_ip_addr}}"
      fos_user_name: admin
      fos_password: fibranne
      https: False

  tasks:

  - name: activate default ipv4 before deleting previously created custom policy
    brocade_security_ipfilter_policy:
      credential: "{{credential}}"
      vfid: -1
      active_policy: "default_ipv4"

  - name: delete custom policy
    brocade_security_ipfilter_policy:
      credential: "{{credential}}"
      vfid: -1
      delete_policies:
        - name: "ipv4_telnet_http"

"""


RETURN = """

msg:
    description: Success message
    returned: success
    type: str

"""


"""
Brocade Fibre Channel ipfilter policy Configuration
"""


from ansible.module_utils.brocade_connection import login, logout, exit_after_login
from ansible.module_utils.brocade_yang import generate_diff
from ansible.module_utils.brocade_security import ipfilter_policy_patch, ipfilter_policy_post, ipfilter_policy_delete, ipfilter_policy_get, to_human_ipfilter_policy, to_fos_ipfilter_policy
from ansible.module_utils.basic import AnsibleModule


def main():
    """
    Main function
    """

    argument_spec = dict(
        credential=dict(required=True, type='dict'),
        vfid=dict(required=False, type='int'),
        throttle=dict(required=False, type='float'),
        ipfilter_policies=dict(required=False, type='list'),
        active_policy=dict(required=False, type='str'),
        delete_policies=dict(required=False, type='list'))

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    input_params = module.params

    # Set up state variables
    fos_ip_addr = input_params['credential']['fos_ip_addr']
    fos_user_name = input_params['credential']['fos_user_name']
    fos_password = input_params['credential']['fos_password']
    https = input_params['credential']['https']
    throttle = input_params['throttle']
    vfid = input_params['vfid']
    ipfilter_policies = input_params['ipfilter_policies']
    active_policy = input_params['active_policy']
    delete_policies = input_params['delete_policies']
    result = {"changed": False}

    if vfid is None:
        vfid = 128

    ret_code, auth, fos_version = login(fos_ip_addr,
                           fos_user_name, fos_password,
                           https, throttle, result)
    if ret_code != 0:
        module.exit_json(**result)

    ret_code, response = ipfilter_policy_get(
        fos_ip_addr, https, auth, vfid, result)
    if ret_code != 0:
        exit_after_login(fos_ip_addr, https, auth, result, module)

    resp_ir = response["Response"]["ipfilter-policy"]

    if isinstance(resp_ir, list):
        c_policies = resp_ir
    else:
        c_policies = [resp_ir]

    # convert REST to human readable format first
    for c_policy in c_policies:
        to_human_ipfilter_policy(c_policy)

    # if active policy is not None, then we make sure
    # the policy is active or activate. and return
    # policy creation or update does not happen at the same
    # time
    if active_policy != None:
        found_disabled_policy = False
        found_active_policy = False
        activate_list = []
        for c_policy in c_policies:
            if c_policy["name"] == active_policy:
                if c_policy["is_policy_active"] == False:
                    found_disabled_policy = True
                    activate_dict = {
                        "name": c_policy["name"],
                        "action": "activate"
                        }
                    activate_list.append(activate_dict)
                else:
                    found_active_policy = True
                    activate_dict = {
                        "name": c_policy["name"],
                        }
                    activate_list.append(activate_dict)

        if found_disabled_policy:
            if not module.check_mode:
                ret_code = ipfilter_policy_patch(
                    fos_ip_addr, https,
                    auth, vfid, result, activate_list)
                if ret_code != 0:
                    exit_after_login(fos_ip_addr, https, auth, result, module)

            result["changed"] = True
        elif found_active_policy:
            result["same active policy"] = activate_list
        else:
            result["failed"] = True
            result["msg"] = "could not find matching policy"

        logout(fos_ip_addr, https, auth, result)
        module.exit_json(**result)

    # if delete policy is not None, then we make sure
    # the policy is not present.
    # policy creation or update does not happen at the same
    # time
    if delete_policies != None:
        to_delete = []
        for delete_policy in delete_policies:
            found = False
            for c_policy in c_policies:
                if c_policy["name"] == delete_policy["name"]:
                    found = True
                    break
            if found:
                to_delete.append(delete_policy)

        if len(to_delete) > 0:
            if not module.check_mode:
                ret_code = ipfilter_policy_delete(
                    fos_ip_addr, https,
                    auth, vfid, result, to_delete)
                if ret_code != 0:
                    exit_after_login(fos_ip_addr, https, auth, result, module)

            result["changed"] = True

        logout(fos_ip_addr, https, auth, result)
        module.exit_json(**result)

    diff_policies = []
    for new_ip in ipfilter_policies:
        for c_policy in c_policies:
            if new_ip["name"] == c_policy["name"]:
                diff_attributes = generate_diff(result, c_policy, new_ip)
                if len(diff_attributes) > 0:
                    result["c_policy"] = c_policy
                    diff_attributes["name"] = new_ip["name"]
                    ret_code = to_fos_ipfilter_policy(diff_attributes, result)
                    if ret_code != 0:
                        exit_after_login(fos_ip_addr, https, auth, result, module)

                    diff_policies.append(diff_attributes)

    add_policies = []
    for new_ip in ipfilter_policies:
        found = False
        for c_policy in c_policies:
            if new_ip["name"] == c_policy["name"]:
                found = True
        if not found:
            new_policy = {}
            for k, v in new_ip.items():
                new_policy[k] = v
            ret_code = to_fos_ipfilter_policy(new_policy, result)
            result["retcode"] = ret_code
            if ret_code != 0:
                exit_after_login(fos_ip_addr, https, auth, result, module)

            add_policies.append(new_policy)

    result["resp_ir"] = resp_ir
    result["ipfilter_policies"] = ipfilter_policies
    result["diff_policies"] = diff_policies
    result["add_policies"] = add_policies
    result["delete_policies"] = delete_policies

    if len(diff_policies) > 0:
        if not module.check_mode:
            ret_code = ipfilter_policy_patch(
                fos_ip_addr, https,
                auth, vfid, result, diff_policies)
            if ret_code != 0:
                exit_after_login(fos_ip_addr, https, auth, result, module)

        result["changed"] = True

    if len(add_policies) > 0:
        if not module.check_mode:
            ret_code = ipfilter_policy_post(
                fos_ip_addr, https,
                auth, vfid, result, add_policies)
            if ret_code != 0:
                exit_after_login(fos_ip_addr, https, auth, result, module)

        result["changed"] = True

    logout(fos_ip_addr, https, auth, result)
    module.exit_json(**result)


if __name__ == '__main__':
    main()
