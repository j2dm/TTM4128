import re
import httplib2
from http.server import BaseHTTPRequestHandler, HTTPServer
from xml.etree import ElementTree
import subprocess

#SNMP PART
host = "129.241.209.30"
ifEntry = "1.3.6.1.2.1.2.2.1.2"
ipAddrTable = "1.3.6.1.2.1.4.20"
sysDescr0 = "1.3.6.1.2.1.1.1.0"

#Runs snmp command in subprocess and returns value of query
def run_cmd(command,oid):
    global host
    proc = subprocess.Popen([command,"-v","2c","-c","ttm4128",host,oid],stdout=subprocess.PIPE)
    out, err = proc.communicate()
    return out

#Converts byte to string
def decode(b):
	return b.decode(encoding='UTF-8')

#runs comand for getting OS, decodes it, and returns string
def getOS():
    os = decode(run_cmd("snmpget",sysDescr0))
    return os

#runs comand for interfaces, and returns a list of their name
def getIF():
    inf = decode(run_cmd("snmpwalk",ifEntry)).split("STRING: ")
    interfaces = []
    i = 0
    for i in inf:
        i = re.sub('IF|-M', '', i[0:7])
        interfaces.append(i)
    interfaces.pop(0)
    return interfaces

#runs command for the IpAddrTable and returns it as a list
def getIP():
    lst = decode(run_cmd("snmpwalk", ipAddrTable)).split("IP-MIB")
    lst.pop(0)
    return lst

#Used to combine interface names and their corresponding elements from IpAddrTable
def InterfaceFix():
    interfaces = getIF()
    adress = getIP()
    mylist = []
    i = 0
    for n in interfaces:
        myString = interfaces[i] + adress[i].split("=",1)[1] + adress[i+(2*len(interfaces))].split("=",1)[1].replace("IpAddress","SubnetMask");
        mylist.append(myString)
        i += 1
    return mylist

#CIM PART
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
    h = httplib2.Http()
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
            data.append({'interface': interfaces[i].text.split("_")[-1], 'IpAdress': ipAddresses[i].text,
                         'SubnetMask': subnetMasks[i].text})
            i += 1
        return data

#uses the previous http request and extract to return content
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

#HTML CONTENT

#Creates HTML for the CIM page
def writeCimPageHTML():
    data = getCIM("IF")
    os = getCIM("OS")
    html= "<h1>CIM System Information</h1>";
    if1 = re.sub("[(){}<>,']" , '', str(data[0]))
    if2 = re.sub("[(){}<>,']" , '', str(data[1]))
    osfix = re.sub("[(){}<>,']" , '', str(os))
    html += "<h2> Operating System: </h2>";
    html += "<ul>";
    html += "<li>" + osfix + "</li>";
    html += "</ul>";
    html += "<h2> Interfaces: </h2>";
    html += "<ul>";
    html += "<li>"+if1+"</li>";
    html += "<li>"+if2+"</li>";
    html += "</ul>";
    html += "<a href='/'>Main Page</a>";
    return html;

#Creates HTML for the snmp page
def writeSnmpPageHTML():
    os = getOS().split("STRING:")
    if1 = InterfaceFix()
    html = "<h1>SNMP System Information</h1>";
    html += "<h2>Operating System</h2>";
    html += "<ul>";
    html += "<li>" + os[1] + "</li>";
    html += "</ul>";
    html += "<h2> Interfaces: </h2>";
    html += "<ul>";
    for n in if1:
        html += "<li>" + n + "</li>";
    html += "</ul>";
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

#SERVER PART

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


