# NotebookCloud: Main App Engine Server

# Uses the Python2.7 runtime and depends on /funcs.py

# Author: Carl Smith, Piousoft
# MailTo: carl.input@gmail.com

import os, random, hashlib

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users

from funcs import *

import sys, urllib, logging

class BaseHandler(webapp.RequestHandler):

    user = users.get_current_user()
    
    def check_user(self):
    
        if not self.user: return None        
        
        try: 
            acc = Account.gql('WHERE user = :1', self.user)[0]
            # upgrade legacy accounts
            if not hasattr(acc, 'ec2_key'): acc.ec2_key = None            
            if not hasattr(acc, 'nb_url'): acc.nb_url = None            
            return acc
        except IndexError: return None


class MainScreen(BaseHandler):
    
    def get(self):

        acc = self.check_user()        
        if acc:

            if not acc.valid:
            
                html = template_dir + 'error.html'
                args = {'error': 'Your account details are invalid.'}
                self.response.out.write(template.render(html, args))
            
            else:
            
                html = template_dir + 'mainscreen.html'
                args = {'username': self.user.email(),
                        'nb_url': acc.nb_url or '',
                        'ec2_key': acc.ec2_key or ''}
                self.response.out.write(template.render(html, args))

        else: self.redirect('/login')


class InstanceInfo(BaseHandler):
    
    def get(self):

        acc = self.check_user()
        if acc:
             
            time.sleep(3) # Takes some time to sync
                
            refresh, html = get_instance_list(
                acc.access_key, acc.secret_key
                )
                
            html += '1' if refresh else '0'

            self.response.out.write(html)

        else: self.redirect('/login')


class ServeDocs(BaseHandler):

    def get(self):
    
        html = template_dir + 'docs.html'
        self.response.out.write(template.render(html, {}))


class ServeForm(BaseHandler):

    def get(self):
        
        user = users.get_current_user()
        if user:

            args = {'username': self.user.email()}
            acc = self.check_user()
            if acc:
                args['access_key'] = acc.access_key
                args['secret_key'] = acc.secret_key
                args['ec2_key'] = acc.ec2_key or ''
                args['nb_url'] = acc.nb_url or ''
            html = template_dir + 'mainform.html'
            self.response.out.write(template.render(html, args))

        else: self.redirect(users.create_login_url('/login'))        


class LaunchVM(BaseHandler):

    def get(self):

        acc = self.check_user()
        if acc:
        
            iclass = [
                't1.micro', 'm1.small', 'm1.medium', 'm1.large', 'm1.xlarge',
                'm2.xlarge', 'm2.2xlarge', 'm2.4xlarge', 'c1.medium',
                'c1.xlarge', 'cg1.4xlarge', 'cc1.4xlarge', 'cc2.8xlarge'
                ][int(self.request.get('iclass'))]
            
            ec2_key = acc.ec2_key
            reservation = str(
                create_vm(acc.access_key, acc.secret_key, acc.user_data, 
                          iclass, ec2_key)[1]).split(':')[1]
            logging.info("recording instance reservation "+reservation)
            acc.reservations.append(reservation)
            acc.put()
            self.redirect('/')

        else: self.redirect('/login')


class ControlVM(BaseHandler):

    def get(self):
        
        acc = self.check_user()
        if acc:
        
            instance_list = [self.request.get('instance')]
            action = self.request.get('action')
            control_vm(action, instance_list, acc.access_key, acc.secret_key)
            self.redirect('/')
            
        else: self.redirect('/login')


class UpdateUserDetails(BaseHandler):

    def post(self):
        
        if not self.user: self.redirect('/login')

        else:
        
            password_0 = self.request.get('pwd0')
            password_1 = self.request.get('pwd1')
            access_key = self.request.get('key0')
            secret_key = self.request.get('key1')
            ec2_key    = self.request.get('ec2key')
            nb_url     = self.request.get('nburl')

            rejection = (
                '<br><br>&nbsp;&nbsp;&nbsp;&nbsp;Your account has '
                '<span class=bolder>not</span> been updated.'
                )
            
            if password_0 != password_1:
            
                html = template_dir + 'error.html'
                args = {'error': 'Passwords must match.'+rejection}
                self.response.out.write(template.render(html, args))
            
            elif not valid_keys(access_key, secret_key):
            
                html = template_dir + 'error.html'
                args = {'error': 'Invalid AWS keys.'+rejection}
                self.response.out.write(template.render(html, args))
                
            elif ec2_key and not valid_ec2_key(access_key, secret_key, ec2_key):
            
                html = template_dir + 'error.html'
                args = {'error': 'Invalid EC2 key.'+rejection}
                self.response.out.write(template.render(html, args))
                
            elif nb_url and not valid_nb_url(nb_url):
            
                html = template_dir + 'error.html'
                args = {'error': 'Invalid Notebook url.'+rejection}
                self.response.out.write(template.render(html, args))
                
            else:
            
                user_data = random.choice(('UK', 'US'))

                for x in range(4):
                    user_data += '|'
                    for y in range(8):
                        user_data += random.choice(
                            'abcdefghijklmnopqrstuvwxyz'
                            )            

                user_data += '|' + hash_password(password_0)
                
                if nb_url:
                    user_data += '|' + nb_url
                try: acc = Account.gql('WHERE user = :1', self.user)[0]
                except:
                
                    acc = Account()
                    acc.user = self.user
                    acc.reservations = []
                
                acc.user_data = user_data
                acc.access_key = access_key
                acc.secret_key = secret_key
                acc.ec2_key = ec2_key
                acc.nb_url = nb_url
                acc.valid = True
                acc.put()
                time.sleep(3) # Takes some time to sync
                
                self.redirect('/')


class DeleteUserDetails(BaseHandler):

    def get(self):
    
        acc = self.check_user()
        if acc: acc.delete()      
            
        self.redirect('/login')
            
            
class Login(BaseHandler):

    def get(self):    
    
        acc = self.check_user()
        
        if acc: 

            self.redirect('/')

        elif self.user:

            html = template_dir + 'create_account.html'
            args = {'email':self.user.email()}
            self.response.out.write(template.render(html, args))

        else: # if the user isn't logged into to google
            
            html = template_dir + 'ask_login.html'
            args = {}
            self.response.out.write(template.render(html, args))


class GoogleLogin(BaseHandler):

    def get(self):
    
        google_login_url = users.create_login_url('/login')
        self.redirect(google_login_url)

class GoogleLogout(BaseHandler):

    def get(self):
    
        google_logout_url = users.create_logout_url('/login')
        self.redirect(google_logout_url)


class Account(db.Model):
    
    user         = db.UserProperty()
    user_data    = db.StringProperty(multiline=False)
    access_key   = db.StringProperty(multiline=False)
    secret_key   = db.StringProperty(multiline=False)
    reservations = db.ListProperty(str)    
    valid        = db.BooleanProperty()
    ec2_key      = db.StringProperty(multiline=False)
    nb_url       = db.StringProperty(multiline=False)


# Map and Serve
routes = [
    ('/login',          Login),
    ('/instance_info',  InstanceInfo),
    ('/google_login',   GoogleLogin),
    ('/google_logout',  GoogleLogout),
    ('/control/.*',     ControlVM),
    ('/mainform',       ServeForm),
    ('/docs',           ServeDocs),
    ('/formsubmit',     UpdateUserDetails),
    ('/delete',         DeleteUserDetails),
    ('/launch/.*',      LaunchVM),
    ('/.*',             MainScreen)
    ]
    
run_wsgi_app(webapp.WSGIApplication(routes, debug=True))
