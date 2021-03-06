# Copyright (c) 2013 Yubico AB
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or
#   without modification, are permitted provided that the following
#   conditions are met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    2. Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

__all__ = ['MetadataResolver', 'create_resolver']

from M2Crypto import X509
from u2flib_server.jsapi import MetadataObject
from u2flib_server.attestation.data import YUBICO
import os
import json


class MetadataResolver(object):

    def __init__(self):
        self._identifiers = {}  # identifier -> Metadata
        self._certs = {}  # Subject -> Cert
        self._metadata = {}  # Cert -> Metadata

    def add_metadata(self, metadata):
        metadata = MetadataObject.wrap(metadata)

        if metadata.identifier in self._identifiers:
            existing = self._identifiers[metadata.identifier]
            if metadata.version <= existing.version:
                return  # Older version
            else:
                # Re-index everything
                self._identifiers[metadata.identifier] = metadata
                self._certs.clear()
                self._metadata.clear()
                for metadata in self._identifiers.values():
                    self._index(metadata)
        else:
            self._identifiers[metadata.identifier] = metadata
            self._index(metadata)

    def _index(self, metadata):
        for cert_pem in metadata.trustedCertificates:
            cert_der = ''.join(cert_pem.splitlines()[1:-1]).decode('base64')
            cert = X509.load_cert_der_string(cert_der)
            subject = cert.get_subject().as_text()
            if subject not in self._certs:
                self._certs[subject] = []
            self._certs[subject].append(cert)
            self._metadata[cert] = metadata

    def resolve(self, cert):
        for issuer in self._certs.get(cert.get_issuer().as_text(), []):
            if cert.verify(issuer.get_pubkey()) == 1:
                return self._metadata[issuer]
        return None


def _load_from_file(fname):
    with open(fname, 'r') as f:
        return json.load(f)


def _load_from_dir(dname):
    return map(_load_from_file,
               [os.path.join(dname, d) for d in os.listdir(dname)
                if d.endswith('.json')])


def _add_data(resolver, data):
    if isinstance(data, list):
        for d in data:
            _add_data(resolver, d)
        return
    elif isinstance(data, basestring):
        if os.path.isdir(data):
            data = _load_from_dir(data)
        elif os.path.isfile(data):
            data = _load_from_file(data)
        return _add_data(resolver, data)
    if data is not None:
        resolver.add_metadata(data)


def create_resolver(data=None):
    resolver = MetadataResolver()
    if data is None:
        data = YUBICO
    _add_data(resolver, data)
    return resolver
