#!/usr/bin/env python
import zmq
from __future__ import print_function
import httplib2
import os
import cv2
import traceback
from datetime import datetime
from apiclient import discovery
import oauth2client

"""
search or create the folder cctvmails to get id
search or create the folder date to get id
upload files to cctvmails/date

"""

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-python-quickstart.json
# SCOPES = 'https://www.googleapis.com/auth/drive.file'
# CLIENT_SECRET_FILE = 'client_secret.json'
# APPLICATION_NAME = 'cctvmails'


class GDrive(object):
    def __init__(self):
        context = zmq.Context()
        self.gdrive_sock = context.socket(zmq.PUSH)
        self.sock.bind("tcp://127.0.0.1:5690")

    def get_cred_service(self, credential_path):
        """Gets valid user credentials from storage.

        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.

        Returns:
            Credentials, the obtained credential.
        """
        """
        try:
            import argparse
            flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
        except ImportError:
            flags = None
        """
        store = oauth2client.file.Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            """flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
            flow.user_agent = APPLICATION_NAME
            if flags:
                credentials = tools.run_flow(flow, store, flags)
            else:  # Needed only for compatibility with Python 2.6
                credentials = tools.run(flow, store)
            print('Storing credentials to ' + credential_path)"""
            print ("Credentials ERROR")
        service = self._get_service(credentials)
        return service

    def _write_creds_file(self, creds_path, user_data):
        cred_format = '{"_module": "oauth2client.client", "scopes": ["https://www.googleapis.com/auth/drive.file"], "token_expiry": "2016-07-10T19:13:36Z", "id_token": null, "access_token": "ya29.Ci8bA-BwrbAdvLayrfWAfw-p-SRWA9o9xgOEyGkp1np7h8ck4G_-kC-9-_lcmbFVIg", "token_uri": "https://accounts.google.com/o/oauth2/token", "invalid": false, "token_response": %s, "client_id": "426166184784-16qo5rpdm73cc4v6vmc9ueocmapkp51r.apps.googleusercontent.com", "token_info_uri": "https://www.googleapis.com/oauth2/v3/tokeninfo", "client_secret": "y_tSC4-99MqY0jhP958f39u7", "revoke_uri": "https://accounts.google.com/o/oauth2/revoke", "_class": "OAuth2Credentials", "refresh_token": "1/JzeOh3WXfyB8mfAG7glnxftw2k-QWQaQ7lOA-wI8Sps", "user_agent": "cctvmails"}' % user_data["gdrive"]
        _file = open(creds_path, "w")
        _file.write(cred_format)
        _file.close()
        _file = open(creds_path + ".id", "w")
        _file.write(user_data["gdrive_parent"])
        _file.close()

    def _get_service(self, credentials):
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('drive', 'v2', http=http)
        return service

    def _get_parent_for_dir(self, directory_structure, drive_service):
        parent = ""
        for directory in directory_structure:
            response = drive_service.files().list(q="title='%s' and mimeType='application/vnd.google-apps.folder'" % directory).execute()
            items = response.get('items', [])
            if not items:
                print('Directory %s not found.' % directory)
                body = {'title': directory,
                        'mimeType': "application/vnd.google-apps.folder"}
                if parent != "":
                    body['parents'] = [{'id': parent}]
                new_folder = drive_service.files().insert(body=body).execute()
                parent = new_folder['id']
            else:
                print('Directory %s found with id %s.' % (directory, items[0]['id']))
                parent = items[0]['id']
        return parent

    def create_dir(self, dir_name, parent="", drive_service):
        print('Directory %s not found.' % directory)
        body = {'title': dir_name,
                'mimeType': "application/vnd.google-apps.folder"}
        if parent != "":
            body['parents'] = [{'id': parent}]
        new_folder = drive_service.files().insert(body=body).execute()
        return new_folder['id']

    def queue_images(self, user_data):
        home_dir = os.path.expanduser('~')
        images_dir = os.path.join(home_dir, '.cctvmails_temp', 'gdrive')
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        creds_path = os.path.join(images_dir, user_data["unique_email"] + ".json")
        if not os.path.isfile(creds_path):
            self._write_creds_file(creds_path, user_data)
        i = 0
        for img in user_data["imgs"]:
            img_name = "%s#%s#%s-%s.jpg" % (user_data["unique_email"], user_data["camera"], user_data["event_time"], str(++i))
            img_path = os.path.join(images_dir, img_name)
            cv2.imwrite(img_path, img)
            try:
                self.sock.send(img_name, zmq.NOBLOCK)
            except Exception as e:
                print ("GDrive push error: " + str(traceback.format_exc()))

    def upload_image(self, img_path, img_name, parent="", service):
        try:
            body = {'title': img_name,
                    'mimeType': "image/jpg"}
            if parent != "":
                body['parents'] = [{'id': parent}]
            new_image = service.files().insert(convert=False, body=body,
                                               media_body=img_path,
                                               fields='mimeType,exportLinks').execute()
            if new_image:
                return True
                # print('Uploaded "%s" (%s)' % (img_path, new_image['mimeType']))
        except Exception as e:
            print ("GDrive upload Error: " + str(traceback.format_exc()))
            return False
