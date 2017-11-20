
import re
import httplib2
from http.server import BaseHTTPRequestHandler, HTTPServer
from xml.etree import ElementTree
import pysnmp
from os import system
import subprocess
import os
import logging
import time
from datetime import datetime
from socket import gethostname


community = "-c ttm4128"
host = "ttm4128.item.ntnu.no"
version = "-v 2c"
ifEntry = "1.3.6.1.2.1.2.2.1.2"
ipAddrTable = "1.3.6.1.2.1.4.20"
sysDescr0 = "1.3.6.1.2.1.1.1.0"



def SNMPcommand(command,oid):
    global host
    global version
    global community
    process = subprocess.Popen([command, "-v", "2c", "-c", "ttm4128v2", host, oid], stdout=subprocess.PIPE)
    out, err = process.communicate()
    print(err)
    return out

def decode(b):
	# Converting from 'b to string
    #print (b);
    print (b.decode(encoding='UTF-8'))
    return b.decode(encoding='UTF-8')

def getIF():
	# Retrieving interfaces
	ifc = SNMPcommand("snmpwalk",ifEntry)#.split("\r\n")
	i = 0
	for item in ifc:
		ifc[i]=item.split("STRING: ")[-1]
		i+=1
		if(len(ifc) == i+1):
			del ifc[i]
			break
	return ifc

def getIP():
	# Retrieving ip information(ipaddr and subnetmask)
	lst = decode(SNMPcommand("snmpwalk","1.3.6.1.2.1.4.20")).split("\r\n")
	newlst = []
	i = 0
	for item in lst:
		if ("iso.3.6.1.2.1.4.20.1.1." in item) or ("ipAdEntAddr" in item):
			newlst.append({"ip":item.split("IpAddress: ")[-1]})
		if ("iso.3.6.1.2.1.4.20.1.3." in item) or ("ipAdEntNetMask" in item):
			newlst[i]["subnet"]=item.split("IpAddress: ")[-1]
			i+=1
	return newlst
def getOS():
    # Retrieve OS information and rewriting it for better printing.
    os = decode(SNMPcommand("snmpget","1.3.6.1.2.1.1.1.0")).split("STRING: ")[-1].split(" ")
    #prettyprint = "%s %s %s" %(os[0],os[3].split("-")[-1],os[2])
    return os



def getSNMP():
	# Gathers data and combines it to ensure that the format is correct. This function is triggered from app.py (webservice)
	os = getOS()
	data = getIP()
	ifs = getIF()
	if len(data) < len(ifs):
		while ((len(data) != len(ifs)) and (len(data)<len(ifs))):
			data.append({'ip':'N/A','subnet':'N/A'})
	i = 0
	for d in data:
		d["interface"]=ifs[i]
		i+=1
	return (data,os)

uri = "http://ttm4128.item.ntnu.no:5988/cimom"

HEAD = {
'Content-type': 'application/xml; encoding="UTF-8"',
'CIMProtocolVersion':'2.0',
'CIMOperation':'MethodCall'
}

# CIM_OperatingSystem
OS_PARAMETER = """<?xml version="1.0" encoding="utf-8" ?>
<CIM CIMVERSION="2.0" DTDVERSION="2.0"><MESSAGE ID="4711" PROTOCOLVERSION="1.0"><SIMPLEREQ><IMETHODCALL NAME="EnumerateInstances"><LOCALNAMESPACEPATH><NAMESPACE NAME="root"></NAMESPACE><NAMESPACE NAME="cimv2"></NAMESPACE></LOCALNAMESPACEPATH>
<IPARAMVALUE NAME="ClassName"><CLASSNAME NAME="CIM_OperatingSystem"/></IPARAMVALUE>
<IPARAMVALUE NAME="DeepInheritance"><VALUE>TRUE</VALUE></IPARAMVALUE>
<IPARAMVALUE NAME="LocalOnly"><VALUE>FALSE</VALUE></IPARAMVALUE>
<IPARAMVALUE NAME="IncludeQualifiers"><VALUE>FALSE</VALUE></IPARAMVALUE>
<IPARAMVALUE NAME="IncludeClassOrigin"><VALUE>TRUE</VALUE></IPARAMVALUE>
</IMETHODCALL></SIMPLEREQ>
</MESSAGE></CIM>"""


# CIM_IPProtocolEndpoint
IF_PARAMETER = """<?xml version="1.0" encoding="utf-8" ?><CIM CIMVERSION="2.0" DTDVERSION="2.0"><MESSAGE ID="4711" PROTOCOLVERSION="1.0"><SIMPLEREQ><IMETHODCALL NAME="EnumerateInstances"><LOCALNAMESPACEPATH><NAMESPACE NAME="root"></NAMESPACE><NAMESPACE NAME="cimv2"></NAMESPACE></LOCALNAMESPACEPATH>
<IPARAMVALUE NAME="ClassName"><CLASSNAME NAME="CIM_IPProtocolEndpoint"/></IPARAMVALUE>
<IPARAMVALUE NAME="DeepInheritance"><VALUE>TRUE</VALUE></IPARAMVALUE>
<IPARAMVALUE NAME="LocalOnly"><VALUE>FALSE</VALUE></IPARAMVALUE>
<IPARAMVALUE NAME="IncludeQualifiers"><VALUE>FALSE</VALUE></IPARAMVALUE>
<IPARAMVALUE NAME="IncludeClassOrigin"><VALUE>TRUE</VALUE></IPARAMVALUE>
</IMETHODCALL></SIMPLEREQ>
</MESSAGE></CIM>"""

#Creates httpRequest
def httpRequest(body):
    h = httplib2.Http(".cache")
    return h.request(uri, "POST", body=body, headers=HEAD)

#extracts the information from XML file for os or interface
def extract(xml, option):
    xml = xml.strip()
    e = ElementTree.fromstring(xml)
    if (option == "OS"):
        out = e.find(".//*[@NAME='ElementName']/VALUE")  # Finds the OS version in the XML
        # print(test.text)
        out = re.split(',?\s(?=\w+=)', out.text)
        return out[4].split('"')[1]
    if (option == "IF"):
        data = []
        interfaces = e.findall(".//*[@NAME='Name']/VALUE")  # Finds all interface names in the XML
        ipAddresses = e.findall(".//*[@NAME='IPv4Address']/VALUE")  # Finds all ips in the XML
        subnetMasks = e.findall(".//*[@NAME='SubnetMask']/VALUE")  # Finds all subnetmasks in XML
        i = 0
        for n in interfaces:
            data.append({'interface': interfaces[i].text.split("_")[-1], 'ip': ipAddresses[i].text,
                         'subnet': subnetMasks[i].text})
            i += 1
        return data

#uses the previous two functions to extract content
def getCIM(option):
    if (option == "OS"):
        (response, content) = httpRequest(OS_PARAMETER)
    elif (option == "IF"):
        (response, content) = httpRequest(IF_PARAMETER)
    else:
        print("Invalid option.")
        return
    if response.status == 200:
        return extract(content.decode(encoding='UTF-8'), option)
    elif response.status == 404:
        print("404")
    else:
        print(response.status, " --- ", response.reason)
    return

#Creates HTML for the CIM page
def writeCimPageHTML():
    data = getCIM("IF")
    os = getCIM("OS")
    html= "<h1>CIM System Information</h1>";
    if1 = re.sub("[(){}<>,']" , '', str(data[0]))
    if2 = re.sub("[(){}<>,']" , '', str(data[1]))
    osfix = re.sub("[(){}<>,']" , '', str(os))
    html += "<ul>";
    html += "<li>"+if1+"</li>";
    html += "<li>"+if2+"</li>";
    html += "<li> Operating System: "+osfix+"</li>";
    html += "</ul>";
    html += "<a href='/'>Main Page</a>";
    return html;

def writeSnmpPageHTML():
    data = getSNMP()
    html = "<h1>CIM System Information</h1>";
    html += "<li>" + str(data) + "</li>";
    html += "<a href='/'>Main Page</a>";
    return html;

#Creates HTML for the main page
def writeFrontPageHTML():
    html = "<h1>Network Administration</h1>";
    html += "<p>Choose management system:</p>";
    html += "<ul>";
    html += "<li><a href='/cim'>CIM</a></li>";
    html += "<li><a href='/snmp'>SNMP</a></li>";
    html += "</ul>";
    return html;


# HTTPRequestHandler class
class testHTTPServer_RequestHandler(BaseHTTPRequestHandler):
    # GET
    def do_GET(self):
        if (self.path == '/'):
            # Main page
            response = 200;
            title = "Choose you're destiny, Bob";
            message = writeFrontPageHTML();
        elif (self.path == '/cim'):
            # CIM subpage
            response = 200;
            title = "CIM System Information";
            message =  writeCimPageHTML();
        elif (self.path == '/snmp'):
            # CIM subpage
            response = 200;
            title = "SNMP System Information";
            message =  writeSnmpPageHTML();
        else:
            response = 400;
            title = "error page"
            message = "<h1>400 error!</h1> An error has occured"
        # Send response status code, header and content
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(bytes(message, "utf8"))
        return

def run():
    print('starting server...')
    server_address = ('127.0.0.1', 8000)
    httpd = HTTPServer(server_address, testHTTPServer_RequestHandler)
    print('running server...')
    httpd.serve_forever()
run()


