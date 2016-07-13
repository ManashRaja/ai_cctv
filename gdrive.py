#!/usr/bin/env python

from __future__ import print_function
import httplib2
import os
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
        pass

    def _get_credentials(self, user_data):
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
        # Prepare the credentials file
        cred_format = '{"_module": "oauth2client.client", "scopes": ["https://www.googleapis.com/auth/drive.file"], "token_expiry": "2016-07-10T19:13:36Z", "id_token": null, "access_token": "ya29.Ci8bA-BwrbAdvLayrfWAfw-p-SRWA9o9xgOEyGkp1np7h8ck4G_-kC-9-_lcmbFVIg", "token_uri": "https://accounts.google.com/o/oauth2/token", "invalid": false, "token_response": %s, "client_id": "426166184784-16qo5rpdm73cc4v6vmc9ueocmapkp51r.apps.googleusercontent.com", "token_info_uri": "https://www.googleapis.com/oauth2/v3/tokeninfo", "client_secret": "y_tSC4-99MqY0jhP958f39u7", "revoke_uri": "https://accounts.google.com/o/oauth2/revoke", "_class": "OAuth2Credentials", "refresh_token": "1/JzeOh3WXfyB8mfAG7glnxftw2k-QWQaQ7lOA-wI8Sps", "user_agent": "cctvmails"}' % user_data["gdrive"]

        home_dir = os.path.expanduser('~')
        credential_dir = os.path.join(home_dir, '.cctvmails_temp', '.credentials')
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir,
                                       '%s.json' % user_data["id"])
        temp_file = open(credential_path, "w")
        temp_file.write(cred_format)
        temp_file.close()

        store = oauth2client.file.Storage(credential_path)
        credentials = store.get()
        os.remove(credential_path)
        if not credentials or credentials.invalid:
            """flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
            flow.user_agent = APPLICATION_NAME
            if flags:
                credentials = tools.run_flow(flow, store, flags)
            else:  # Needed only for compatibility with Python 2.6
                credentials = tools.run(flow, store)
            print('Storing credentials to ' + credential_path)"""
            print ("Credentials ERROR")
        return credentials

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

    def upload_image(self, user_data, img):
        try:
            credentials = self._get_credentials(user_data)
            service = self._get_service(credentials)
            body = {'title': os.path.basename(img),
                    'mimeType': "image/jpg"}

            date = datetime.now().strftime('%d-%m-%Y')
            directory_structure = ['cctvmails', date, user_data["camera"]]
            parent = self._get_parent_for_dir(directory_structure, service)
            if parent != "":
                body['parents'] = [{'id': parent}]
            new_image = service.files().insert(convert=False, body=body,
                                               media_body=img,
                                               fields='mimeType,exportLinks').execute()
            if new_image:
                print('Uploaded "%s" (%s)' % (img, new_image['mimeType']))
        except Exception as e:
            print ("GDrive upload Error: " + str(traceback.format_exc()))
