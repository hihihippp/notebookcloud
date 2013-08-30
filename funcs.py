# NotebookCloud: EC2 Functions

# Uses the Python2.7 runtime and depends on /boto
# /main.py does import * all on this file

# Author: Carl Smith, Piousoft
# MailTo: carl.input@gmail.com

import random, hashlib, time, os

from google.appengine.api import urlfetch
from google.appengine.ext.webapp import template

import boto
from boto.ec2.connection import EC2Connection

#
# work around broken certificate validation in app engine, for now.
# This also requires that you call EC2Connection(... is_secure=False)
#
if not boto.config.has_section('Boto'):
    boto.config.add_section('Boto')
boto.config.set('Boto', 'https_validate_certificates', 'False')

template_dir = os.path.join(os.path.dirname(__file__), 'templates/')


def valid_keys(access_key, secret_key):
    
    try: EC2Connection(access_key, secret_key, is_secure=False)\
            .get_all_instances()       
    except: return False
    return True

def valid_ec2_key(access_key, secret_key, key_name):
    
    try: EC2Connection(access_key, secret_key, is_secure=False)\
            .get_all_key_pairs([key_name])[0]       
    except: return False
    return True

def hash_password(password):
    
    '''
    This function is derived from passwd in IPython.lib. It hashes a
    password correctly for use with the IPython notebook server.
    '''
    
    h = hashlib.new('sha1')
    salt = ('%0' + str(12) + 'x') % random.getrandbits(48)
    h.update(password + salt)
    
    return ':'.join(('sha1', salt, h.hexdigest()))


def get_instance_list(access_key, secret_key):
    
    '''
    This function returns the html for the instance info that is displayed
    by the client in the Your Notebook Servers panel.
    '''
    
    tab = '&nbsp;'*4 
    html_output = ''
    refresh = False
    
    connection = EC2Connection(access_key, secret_key, is_secure=False)
    
    reservations = connection.get_all_instances()
    instances = [inst for res in reservations for inst in res.instances]

    for inst in instances:
        
        ours  = inst.image_id == 'ami-ebbff282'
        lives = (inst.state != 'terminated')
        
        if ours and lives:

            dns_name      = inst.public_dns_name
            state         = inst.state
            instance_type = inst.instance_type 
            instance_id   = inst.id 
            date, time    = inst.launch_time.split('T')
            key_name      = inst.key_name
        
            time=time[:-5]

            transitional = False
            if state in ('shutting-down', 'pending', 'stopping', 'running'):
                transitional = True
        
            # note: the variable `state` below will be changed to 'serving' if the
            # IPython server is online. nbc has no running state, all running
            # servers are classed as booting or serving
            if state == 'running': state = 'booting'
            
            html_output += (
                '<div class=instance>Instance id: <b>{}</b>Type: <b>{}</b>'
                'Started: <b>{}</b> ~ <b>{}</b><br>'
                ).format(instance_id + tab, instance_type + tab, time, date)
        
            if dns_name:
            
                if key_name is not None:
                    
                    html_output += ( tab +
                        'ssh: <span id="serving">ubuntu@{} (key={})</span><br>'
                        ).format(dns_name, key_name)

                try: # check if the instance is actively serving
            
                    urlfetch.fetch(
                        'https://'+dns_name+':8888',
                        validate_certificate=False,
                        deadline=25
                        ).content
                                
                except:
            
                    state = '<b>'+state+'</b>'
                    html_output += tab + "State: "+ state
                
                else:
            
                    html = template_dir + 'serving_buttons.html'
                    args = {'instance': instance_id}
                    serving_buttons = template.render(html, args)
                
                    html_output += (
                        '{}Serving at <a id="serving" '
                        'href="https://{}:8888">{}:8888</a>{}'
                        ).format(tab, dns_name, dns_name, serving_buttons)
                
                    # now we know we're running, not booting
                    transitional = False

            else:
        
                if state == 'stopped':
            
                    state = '<b>stopped</b>'
                    html = template_dir + 'stopped_buttons.html'
                    args = {'instance': instance_id}
                    stopped_buttons = template.render(html, args)
                    html_output += tab + 'State: ' + state + stopped_buttons
            
                else:
            
                    state = '<b>'+state+'</b>'
                    html_output += tab + 'State: ' + state

            html_output += '</div>'
        
            if transitional: refresh = True
    

    if not html_output:
    
        html_output = (
            '<br>'+tab+'No instances (launched from NotebookCloud) '
            'exist on your AWS account. <br><br>'
            )
    
    return refresh, html_output


def create_vm(access_key, secret_key, user_details, instance_class, ec2_key):

    connection = EC2Connection(access_key, secret_key, is_secure=False)

    group_name  = 'notebookcloud_group'
    description = 'NotebookCloud: Default Security Group.'
    
    try: group = connection.create_security_group(group_name, description)
    except: pass
    else: group.authorize('tcp', 8888,8888, '0.0.0.0/0')
    security_groups = ['notebookcloud_group']

    if ec2_key:

        group_name  = 'notebookcloud_ssh_group'
        description = 'NotebookCloud: SSH Security Group.'
    
        try: group = connection.create_security_group(group_name, description)
        except: pass
        else: group.authorize('tcp', 22, 22, '0.0.0.0/0')
        security_groups.append('notebookcloud_ssh_group')

    reservation = connection.run_instances(
        'ami-ebbff282',
        instance_type=instance_class,
        security_groups=security_groups,
        key_name=ec2_key,
        user_data=user_details,
        max_count=1
        )
        
    return connection, reservation
    
    
def control_vm(action, instance_list, access_key, secret_key):
    
    connection = EC2Connection(access_key, secret_key, is_secure=False)
    
    if action == 'terminate':
        connection.terminate_instances(instance_ids=instance_list)
    
    elif action == 'stop':
        connection.stop_instances(instance_ids=instance_list)

    elif action == 'start':
        connection.start_instances(instance_ids=instance_list)
        
    elif action == 'reboot':
        connection.reboot_instances(instance_ids=instance_list)
