#!/usr/bin/python
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation; either version 3, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.

"Implementación pythónica de cliente SOAP"
from simplejson import OrderedDict

__author__ = "Mariano Reingart (mariano@nsis.com.ar)"
__copyright__ = "Copyright (C) 2008 Mariano Reingart"
__license__ = "LGPL 3.0"
__version__ = "1.0"

import httplib2
from .simplexml import SimpleXMLElement


class SoapFault(RuntimeError):
    def __init__(self, faultcode, faultstring):
        self.faultcode = faultcode
        self.faultstring = faultstring


class SoapClient(object):
    "Manejo de Cliente SOAP Simple (símil PHP)"

    def __init__(self, location=None, action=None, namespace=None,
                 cert=None, trace=False, exceptions=False, proxy=None):
        self.certssl = cert
        self.keyssl = None
        self.location = location  # server location (url)
        self.action = action  # SOAP base action
        self.namespace = namespace  # message
        self.trace = trace  # show debug messages
        self.exceptions = exceptions  # lanzar execpiones? (Soap Faults)

        if not proxy:
            self.http = httplib2.Http('.cache', disable_ssl_certificate_validation=True)
        else:
            import socks
            ##httplib2.debuglevel=4
            self.http = httplib2.Http(disable_ssl_certificate_validation=True, proxy_info=httplib2.ProxyInfo(
                proxy_type=socks.PROXY_TYPE_HTTP, **proxy))
        # if self.certssl: # esto funciona para validar al server?
        #    self.http.add_certificate(self.keyssl, self.keyssl, self.certssl)

    def __getattr__(self, attr):
        "Devuelve un pseudo-método que puede ser llamado"
        return lambda self=self, xml="", *args, **kwargs: self.call(attr, xml, *args, **kwargs)

    def call(self, method, *args, **kwargs):
        "Prepara el xml y realiza la llamada SOAP, devuelve un SimpleXMLElement"
        # Mensaje de Solicitud SOAP básico:
        xml = """<?xml version="1.0" encoding="utf-8"?> 
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
    xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
    xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"> 
<soap:Body>
    <%(method)s xmlns="%(namespace)s">
    </%(method)s>
</soap:Body>
</soap:Envelope>""" % dict(method=method, namespace=self.namespace)
        request = SimpleXMLElement(xml)
        # parsear argumentos
        for k, v in list(kwargs.items()):  # dict: tag=valor
            self.parse(getattr(request, method), k, v)
        self.xml_request = request.asXML()
        self.xml_response = self.send(method, self.xml_request)
        response = SimpleXMLElement(self.xml_response.decode())
        if self.exceptions and ("soapenv:Fault" in response or "soap:Fault" in response):
            raise SoapFault(str(response.faultcode), str(response.faultstring))
        return response

    def parse(self, node, tag, value, add_child=True):
        "Analiza un objeto y devuelve su representación XML"
        if isinstance(value, (dict, OrderedDict)):  # serializar diccionario (<key>value</key>)
            child = add_child and node.addChild(tag) or node
            for k, v in list(value.items()):
                self.parse(child, k, v)
        elif isinstance(value, tuple):  # serializar diccionario (<key>value</key>)
            child = add_child and node.addChild(tag) or node
            for k, v in value:
                self.parse(getattr(node, tag), k, v)
        elif isinstance(value, list):  # serializar listas
            child = node.addChild(tag)
            for t in value:
                self.parse(child, tag, t, False)
        else:  # el resto de los objetos se convierten a string
            node.addChild(tag, str(value))  # habria que agregar un método asXML?

    def send(self, method, xml):
        "Envía el pedido SOAP por HTTP (llama al método con el xml como cuerpo)"
        if self.location == 'test': return
        location = "%s" % self.location  # ?op=%s" % (self.location, method)
        headers = {
            'Content-type': 'text/xml; charset="UTF-8"',
            'Content-length': str(len(xml)),
            "SOAPAction": "\"%s%s\"" % (self.action, method)
        }
        if self.trace:
            print("-" * 80)
            print("POST %s" % location)
            print('\n'.join(["%s: %s" % (k, v) for k, v in list(headers.items())]))
            print("\n%s" % xml)
        response, content = self.http.request(
            location, "POST", body=xml, headers=headers)
        self.response = response
        self.content = content
        if self.trace:
            print()
            print('\n'.join(["%s: %s" % (k, v) for k, v in list(response.items())]))
            print(content)
            print("=" * 80)
        return content


def parse_proxy(proxy_str):
    "Parses proxy address user:pass@host:port into a dict suitable for httplib2"
    proxy_dict = {}
    if proxy_str is None:
        return
    if "@" in proxy_str:
        user_pass, host_port = proxy_str.split("@")
    else:
        user_pass, host_port = "", proxy_str
    if ":" in host_port:
        host, port = host_port.split(":")
        proxy_dict['proxy_host'], proxy_dict['proxy_port'] = host, int(port)
    if ":" in user_pass:
        proxy_dict['proxy_user'], proxy_dict['proxy_pass'] = user_pass.split(":")
    return proxy_dict
