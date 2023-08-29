import os
import logging

import requests
import pynetbox

log = logging.getLogger(__name__) # TODO central logger defination

class Client(): ## netbox.Client()
    def __init__(self):
        # build the client and initalze the constructs
        self.client = self.build_client(url=os.getenv('NETBOX_URL'), token=os.getenv('NETBOX_TOKEN'))
        self.reload()

    # load any data that needs to be loaded
    def reload(self):
        """Load the data and cache locally, to avoid a lot of slow network calls"""
        log.info("Loading sites")
        self.sites = self.load_sites()
        self.site_names = list(self.sites)
        log.info(f"Loaded: {self.site_names}")

    # build a client for communicating with an instance of netbox
    def build_client(self, url:str, token:str):
        """Given a secure token, build a client to communicate with a netbox instance"""
        client = pynetbox.api(url, token)

        # create a custom session to disable SSL validation, as per
        # https://pynetbox.readthedocs.io/en/latest/advanced.html#ssl-verification
        # FIXME This should be removed as soon as real certs are in place.
        session = requests.Session()
        session.verify = False
        client.http_session = session
        
        return client

    def site(self, slug:str):
        return self.sites[slug]

    def load_sites(self):
        """Load the list of sites from the netbox client"""
        sites = {}
        for site in self.client.dcim.sites.all():
            sites[site.slug] = site
            
        return sites
    
    def format_site(self, site):
        #return f"**({site.url})[{site.slug}]** {site.name} {site.last_updated}"
        url = site.url.replace('/api', '') # strip the /api from the url
        return f"**[{site.slug}]({url})** - {site.name}"
    
    def format_sites(self):
        msg = ""
        for site in self.sites.values():
            msg += self.format_site(site) + '\n'
        return msg