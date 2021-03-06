# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import httplib
import urlparse

from glance.common import exception
import glance.store
import glance.store.location

glance.store.location.add_scheme_map({'http': 'http',
                                      'https': 'http'})


class StoreLocation(glance.store.location.StoreLocation):

    """Class describing an HTTP(S) URI"""

    def process_specs(self):
        self.scheme = self.specs.get('scheme', 'http')
        self.netloc = self.specs['netloc']
        self.user = self.specs.get('user')
        self.password = self.specs.get('password')
        self.path = self.specs.get('path')

    def _get_credstring(self):
        if self.user:
            return '%s:%s@' % (self.user, self.password)
        return ''

    def get_uri(self):
        return "%s://%s%s%s" % (
            self.scheme,
            self._get_credstring(),
            self.netloc,
            self.path)

    def parse_uri(self, uri):
        """
        Parse URLs. This method fixes an issue where credentials specified
        in the URL are interpreted differently in Python 2.6.1+ than prior
        versions of Python.
        """
        pieces = urlparse.urlparse(uri)
        assert pieces.scheme in ('https', 'http')
        self.scheme = pieces.scheme
        netloc = pieces.netloc
        path = pieces.path
        try:
            if '@' in netloc:
                creds, netloc = netloc.split('@')
            else:
                creds = None
        except ValueError:
            # Python 2.6.1 compat
            # see lp659445 and Python issue7904
            if '@' in path:
                creds, path = path.split('@')
            else:
                creds = None
        if creds:
            try:
                self.user, self.password = creds.split(':')
            except ValueError:
                reason = ("Credentials '%s' not well-formatted."
                          % "".join(creds))
                raise exception.BadStoreUri(uri, reason)
        else:
            self.user = None
        if netloc == '':
            reason = "No address specified in HTTP URL"
            raise exception.BadStoreUri(uri, reason)
        self.netloc = netloc
        self.path = path


class HTTPBackend(glance.store.Backend):
    """ An implementation of the HTTP Backend Adapter """

    @classmethod
    def get(cls, location, expected_size, options=None, conn_class=None):
        """
        Takes a `glance.store.location.Location` object that indicates
        where to find the image file, and returns a generator from Swift
        provided by Swift client's get_object() method.

        :location `glance.store.location.Location` object, supplied
                  from glance.store.location.get_location_from_uri()
        """
        loc = location.store_location
        if conn_class:
            pass  # use the conn_class passed in
        elif loc.scheme == "http":
            conn_class = httplib.HTTPConnection
        elif loc.scheme == "https":
            conn_class = httplib.HTTPSConnection
        else:
            raise glance.store.BackendException(
                "scheme '%s' not supported for HTTPBackend")

        conn = conn_class(loc.netloc)
        conn.request("GET", loc.path, "", {})

        try:
            return glance.store._file_iter(conn.getresponse(), cls.CHUNKSIZE)
        finally:
            conn.close()
