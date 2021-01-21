import asyncore
from smtpd import SMTPServer


class EmlServer(SMTPServer):
    def __init__(self, local_address, remote_address):
        SMTPServer.__init__(self, local_address, remote_address)

    def process_message(self, peer, mailfrom, rcpttos, data):
        print "Email from:", mailfrom, "\nData:", data


def run():
    print "Running"
    server = EmlServer(('0.0.0.0', 587), None)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass


run()
