#!/usr/bin/python
'''
usage: getDefect.py [-h] [-s SERVER] [-p PORT] [-u USER]
                                    [-c PASSWORD] [-n PROJECTNAME]
                                    [-d LASTTRIAGED]

python getDefect_v1.4b.py --server [Coverity_Connect_ip_address] --user admin --password synopsys --project WebGoat3 

getMergedDefects for all streams in a projects which were triaged more
recently than the lasttriaged date

optional arguments:
  -h, --help            show this help message and exit
  -s SERVER, --server SERVER
                        server (default: localhost)
  -p PORT, --port PORT  port (default: 8080)
  -u USER, --user USER  user (default: admin)
  -c PASSWORD, --password PASSWORD
                        password (default: coverity)
  -n PROJECTNAME, --projectname PROJECTNAME
                        projectname (default: "*", meaning all)
  -d LASTTRIAGED, --lasttriaged LASTTRIAGED
                        last triaged after (default:"2016-10-10T01:01:01")

'''
# This script requires suds that provides SOAP bindings for python.
# Download suds from https://fedorahosted.org/suds/
#   unpack it and then run:
#     python setup.py install
#
#   or unpack the 'suds' folder and place it in the same place as this script
from suds.client import Client
from suds.wsse import Security, UsernameToken
#
#For basic logging
import logging
logging.basicConfig()

import argparse

import inspect      # for getKeys()
import base64, zlib # for decoding file contents

from collections import Counter
from jira import JIRA
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import datetime
begin = datetime.datetime.now()
# -----------------------------------------------------------------------------
class WebServiceClient:
    def __init__(self, webservice_type, host, port, ssl, username, password):
        url = ''
        if (ssl):
            url = 'https://' + host + ':' + port
        else:
            url = 'http://' + host + ':' + port
        if webservice_type == 'configuration':
            self.wsdlFile = url + '/ws/v9/configurationservice?wsdl'
        elif webservice_type == 'defect':
            self.wsdlFile = url + '/ws/v9/defectservice?wsdl'
        else:
            raise "unknown web service type: " + webservice_type

        self.client = Client(self.wsdlFile)
        self.security = Security()
        self.token = UsernameToken(username, password)
        self.security.tokens.append(self.token)
        self.client.set_options(wsse=self.security)

    def getwsdl(self):
        print(self.client)

# -----------------------------------------------------------------------------
class DefectServiceClient(WebServiceClient):
    def __init__(self, host, port, ssl, username, password):
        WebServiceClient.__init__(self, 'defect', host, port, ssl, username, password)

# -----------------------------------------------------------------------------
class ConfigServiceClient(WebServiceClient):
    def __init__(self, host, port, ssl, username, password):
        WebServiceClient.__init__(self, 'configuration', host, port, ssl, username, password)
    def getProjects(self):
        return self.client.service.getProjects()		

def getKeys(obj):
    return inspect.getmembers(obj)[6][1]

issue_dict = {}
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    #
    parser = argparse.ArgumentParser(description='getMergedDefects for all streams in a projects which were triaged more recently than the lasttriaged date')
    parser.add_argument('-s','--server',  default= 'localhost', help='server (default: localhost)')    
    parser.add_argument('-p','--port',  default= '8080', help='port (default: 8080)')    
    parser.add_argument('-u','--user',  default= 'admin', help='user (default: admin)')    
    parser.add_argument('-c','--password',  default= 'coverity', help='password (default: coverity)')    
    parser.add_argument('-n','--projectname',  default= '*', help='projectname (default: "*", meaning all)')    
    parser.add_argument('-d','--lasttriaged',  default= '2016-10-10T01:01:01', help='last triaged after (default:"2016-10-10T01:01:01")') 
    parser.add_argument('-js','--jserver',  default= '*', help='Jira server URL (eg. http://192.168.29.128:8090)')
    parser.add_argument('-ju','--juser',  default= '*', help='Jira user')
    parser.add_argument('-jp','--jpassword',  default= '*', help='Jira user password')
    parser.add_argument('-k','--jkey',  default= '*', help='Jira project key (eg. Jira project WebGoat with key WG)')
    parser.add_argument('-f','--pdf',  default= 'Coverity-Security-Report.pdf', help='Coverity PDF report file name to attach on Jira ticket (eg. Coverity-Security-Report.pdf)')
    parser.add_argument('-v','--csv',  default= 'defect.csv', help='Coverity CSV report file name to attach on Jira ticket (eg. defect.csv))')
    args = parser.parse_args()
    #
    host = args.server #'localhost'
    port = args.port   #'8080'
    ssl = False
    username = args.user #'admin'
    password = args.password #'coverity'
    jserver = args.jserver #jira server URL
    juser = args.juser #jira user account
    jpassword = args.jpassword #jira user password
    jkey = args.jkey #'WG'
    pdf = args.pdf #'Coverity-Security-Report.pdf'
    csv = args.csv #'defect.csv'
    #
    projectpattern=args.projectname
    cutoffdate=args.lasttriaged
    #---------------------------------------------------------
    list_merged_defects = True  #Before drilling down
    drill_down = True
    list_md_detection_history = False
    list_md_history = False
    list_stream_defects = True
    list_sd_history= False
    list_sd_defect_instances= True
    #
    max_retrieved = 2
    #----------------------------------------------------------
    defectServiceClient = DefectServiceClient(host, port, ssl, username, password)
    configServiceClient = ConfigServiceClient(host, port, ssl, username, password)
    print '------------getProjects'
    projectIdDO = configServiceClient.client.factory.create('projectFilterSpecDataObj')
    projectIdDO.namePattern=projectpattern 
    projectIdDO.includeStreams=True
    results = configServiceClient.client.service.getProjects(projectIdDO)
    for v in results:
        print 'Project:', v.id.name,
        if hasattr(v,'description'):
            print v.description
        else:
            print '-'
        if hasattr(v,'streams'):
            print 'Project stream length is ', len(v.streams)
            #print v.streams.streamIdDataObj
            for s in v.streams:
                print 'Stream:',s.id.name, 
                if hasattr(s,'description'):
                    print s.description, 
                else:
                    print '-',
                print s.language,s.triageStoreId.name, s.componentMapId.name, s.outdated, s.autoDeleteOnExpiry, 
                print s.enableDesktopAnalysis, 
                if hasattr(s,'summaryExpirationDays'):
                    print s.summaryExpirationDays
                else:
                    print '-'
                mds_retrieved=0
                totalrecords=1 #try at least one
                print '------------getMergedDefectsForStreams'
                mergedDefectFilterDO = defectServiceClient.client.factory.create('mergedDefectFilterSpecDataObj')
                mergedDefectFilterDO.classificationNameList= ["Unclassified","Pending","Bug"]  

                pageSpecDO = defectServiceClient.client.factory.create('pageSpecDataObj')
                pageSpecDO.pageSize = 50
                pageSpecDO.sortField = 'cid'
                #
                # Grammar for snapshot show selector
                    # Snapshot ID
                    # first()
                    # last()
                    # expression, expression
                    # expression..expression
                    # lastBefore(expression)
                    # lastBefore(date)
                    # firstAfter(expression)
                    # firstAfter(date)
                    # Examples
                    # 10017, 10021
                    # lastBefore(last())
                    # firstAfter(2012-11-30)
                    # firstAfter(1 day ago)..last()
                
                snapshotScopeDO = defectServiceClient.client.factory.create('snapshotScopeSpecDataObj')

                projectId = defectServiceClient.client.factory.create('projectIdDataObj')
                projectId.name = projectpattern

                filterSpec = defectServiceClient.client.factory.create('snapshotScopeDefectFilterSpecDataObj')
                #filterSpec.externalReference = 0
                #filterSpec.statusNameList = ['New', 'Triaged']
                #filterSpec.classificationNameList = ["Unclassified","Pending","Bug"] 
                #print 'Snapshot list len ' + str(len(configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec)))                
                if len(configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec)) > 1:
                    #print 'Snapshot list length ' + str(len(configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec))) 
                    snapshotScopeDO.compareOutdatedStreams = True
                    snapshotScopeDO.compareSelector = 'lastBefore(last())'
                    snapshotScopeDO.showOutdatedStreams = True
                    snapshotScopeDO.showSelector = 'last()' #'first()..last()'
                    filterSpec.issueComparison = 'ABSENT'
                #pageSpec = defectServiceClient.client.factory.create('pageSpecDataObj')
                #pageSpec.startIndex = 0
                #pageSpec.pageSize = 1000
                #snapshotScope = defectServiceClient.client.factory.create('snapshotScopeSpecDataObj')
                #snapshotScope.showSelector = snapshot_id
                #print 'Check snapshot compare'
                #print snapshotScopeDO.compareOutdatedStreams
                #print snapshotScopeDO.compareSelector
                #print snapshotScopeDO.showOutdatedStreams
                #print snapshotScopeDO.showSelector
                #print filterSpec.issueComparison
                cid_list = defectServiceClient.client.service.getMergedDefectsForSnapshotScope(projectId, filterSpec, pageSpecDO, snapshotScopeDO)
                print 'Snapshot len is ' + str(len(configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec)))

                print 'Check no of record in CID list ' + str(cid_list.totalNumberOfRecords)
 
                while mds_retrieved < totalrecords and mds_retrieved < max_retrieved :
                    pageSpecDO.startIndex=mds_retrieved
                    mergedDefects = defectServiceClient.client.service.getMergedDefectsForStreams(s.id, mergedDefectFilterDO, pageSpecDO,snapshotScopeDO)
                    #print mergedDefects.__keylist__
                    totalrecords=mergedDefects.totalNumberOfRecords
                    if mds_retrieved == 0:
                        print 'totalrecords: ',totalrecords
                    if totalrecords > 0 :
                        thispage=len(mergedDefects.mergedDefectIds)
                        mds_retrieved += thispage
                        #
                        # FOR current attributes no drill down necessary
                        #
                        if list_merged_defects == True:
                            for md in mergedDefects.mergedDefects:
                                #print md.__keylist__
                                #
                                #alternatively:  md.cid, md.checkerName ... would  also work
                                #                       
                                md_keys=md.__keylist__
#                                 ['checkerName', 'cid', 'componentName', 'cwe', 'defectStateAttributeValues', 
#                                          'displayCategory', 'displayImpact', 'displayIssueKind', 'displayType', 'domain', 
#                                          'filePathname', 'firstDetected', 'firstDetectedBy', 'firstDetectedSnapshotId', 
#                                          'firstDetectedStream', 'firstDetectedVersion', 'functionDisplayName', 'functionName', 
#                                          'issueKind', 'lastDetected', 'lastDetectedSnapshotId', 'lastDetectedStream', 
#                                          'lastDetectedVersion', 'lastTriaged', 'mergeKey', 'occurrenceCount']
                                for k in md_keys:
                                    if k not in ['defectStateAttributeValues']:
                                        print k,'=' ,md[k]
                                    else:
                                        for a in md[k]:
                                            print a.attributeDefinitionId.name,'=',
                                            if hasattr(a.attributeValueId, 'name'):
                                                print a.attributeValueId.name
                                            else:
                                                print a.attributeValueId
        
                        #
                        # DRILL DOWN FOR 
                        #    Detection History
                        #    Triage History
                        #    Stream Defects
                        #        optional Defect Instances and Defect History
                        #
                        if drill_down == True:
                            '''               
                            ####
                            #original code for defect capture
                            for mdid in mergedDefects.mergedDefectIds:
                                print mdid.cid,mdid.mergeKey
                                #
                                #    DRILL DOWN Detection History
                                #
                                #
                                if list_md_detection_history == True :
                                    print '------------getMergedDefectDetectionHistory'
                                    defectDetectionHistory = defectServiceClient.client.service.getMergedDefectDetectionHistory(mdid, s.id)
                                    for mdh in defectDetectionHistory:
                                        print mdh.userName, mdh.defectDetection, mdh.detection, mdh.snapshotId, mdh.streams[0].name
                                #
                                #    DRILL DOWN Triage History
                                #
                                #
                                if list_md_history == True :
                                    print '------------getMergedDefectHistory'
                                    defectChanges = defectServiceClient.client.service.getMergedDefectHistory(mdid, s.id)
                                    for dc in defectChanges:
                                        #print getKeys(dc) 
                                        print dc.userModified,dc.dateModified,
                                        for sa in dc.affectedStreams:
                                            print sa.name
                                        for ca in dc.attributeChanges:
                                            if ca :
                                                for fc in ca:
                                                    print fc[0],'=',fc[1]#.fieldName,fc.oldValue,fc.newValue
                                        if hasattr(dc,'comments'):
                                            print 'comments = ',dc.comments
                                            #issue_dict[str(sd.cid).rstrip('L')] = {'Comments': sd.checkerName}
                                #
                                #    DRILL DOWN Stream Defects
                                #        optionally also get Triage History and Defect Instances
                                #
                                if list_stream_defects == True:
                                
                                    defect_dict = {} 
                                    
                                    print '------------getStreamDefects'
                                    streamDefectFilterDO = defectServiceClient.client.factory.create('streamDefectFilterSpecDataObj')
                                    streamDefectFilterDO.streamIdList=[s.id]
                                    streamDefectFilterDO.defectStateStartDate = '2010-09-05'
                                    streamDefectFilterDO.defectStateEndDate = '2020-10-05'       
                                    streamDefectFilterDO.includeDefectInstances = list_sd_defect_instances
                                    streamDefectFilterDO.includeHistory = list_sd_history 
                                    streamDefects = defectServiceClient.client.service.getStreamDefects(mdid, streamDefectFilterDO)
                                    for sd in streamDefects:
                                        print '<CID> ',sd.cid,' <Checker> ',sd.checkerName,' <Domain> ',sd.domain
                                        issue_dict[str(sd.cid).rstrip('L')] = {'CID': str(sd.cid).rstrip('L'), 'Checker': sd.checkerName, 'Domain': sd.domain}
                                        
                                        #print sd.id.defectTriageId, sd.id.defectTriageVerNum, sd.id.id,sd.id.verNum
                                        for a in sd.defectStateAttributeValues:
                                            print a.attributeDefinitionId.name,'=',a.attributeValueId.name
                                        if hasattr(sd,'history'):
                                            for dh in sd.history:
                                                print getKeys(dh)
                                                print dh.dateCreated,dh.userCreated
                                                for a in dh.defectStateAttributeValues:
                                                    print a.attributeDefinitionId.name,'=',a.attributeValueId.name
                                        if hasattr(sd,'defectInstances'):
                                           for di in sd.defectInstances:
                                                #print di.category.name,di.category.displayName
                                                #print di.checkerName
                                                #print di.component
                                                #print di.cwe
                                                #print di.domain
                                                #print di.extra
                                                print '<Function> ', di.function.functionDisplayName#, di.function.functionMangledName, di.function.functionMergeName
                                                print '<Path>', di.function.fileId.filePathname, di.function.fileId.contentsMD5 
                                                print '<ID> ', di.id.id
                                                print '<Impact>', di.impact.displayName,di.impact.name 
                                                issue_dict[str(sd.cid).rstrip('L')].update({'Function': di.function.functionDisplayName+' '+di.function.functionMangledName+' '+di.function.functionMergeName})
                                                for ik in di.issueKinds:
                                                    print '<Issue Kind> ', ik.displayName, ik.name
                                                    issue_dict[str(sd.cid).rstrip('L')].update({'Issue Kind': ik.displayName+' '+ik.name})
                                                print '<Effect> ', di.localEffect
                                                print '<Description> ', di.longDescription
                                                issue_dict[str(sd.cid).rstrip('L')].update({'Effect': di.localEffect, 'Description' : di.longDescription})
                                                #print di.type.displayName, di.type.name
                                                for e in di.events:
                                                    if e.main:
                                                        #print e.main,e.polarity,e.eventKind, e.eventNumber, e.eventSet, e.eventTag 
                                                        print '<LineNumber> ', e.lineNumber
                                                        issue_dict[str(sd.cid).rstrip('L')].update({'LineNumber': e.lineNumber})
                                                        #print '-FilePathName- ', e.fileId.filePathname, e.fileId.contentsMD5
                                                        #print '------------getFileContents'
                                                        v = defectServiceClient.client.service.getFileContents(s.id, di.function.fileId)
                                                        decompressedContent=zlib.decompress(bytes(bytearray(base64.b64decode(v['contents']))), 15+32)
                                                        #print 'decompressed:',len(decompressedContent) ,"bytes"
                                                        print '<Code_snippet> '
                                                        if len(decompressedContent) > 0:
                                                            ln=e.lineNumber-5
                                                            snippet=()
                                                            for l in decompressedContent.split('\n')[e.lineNumber-5:e.lineNumber+5]:
                                                                print ln,'>',l
                                                                snippet += ln,'>',l,'\r\n'
                                                                ln += 1
                                                            issue_dict[str(sd.cid).rstrip('L')].update({'Code_snippet': snippet})
                                                        print '<Defect Content End> '
                            ####
                            ''' 
                            #---
                            #Using snapshots comparison 
                            #print '\n'+'cid_list type is ' + str(type(cid_list))
                            #print len(cid_list)
                            print '\nTotal number of new record is '+ str(cid_list.totalNumberOfRecords)
                            print len(configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec))
                            print 'time taken 1 is', datetime.datetime.now() - begin
                            if not configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec):      
                                print 'No Coverity Connect snapshot exist, please conduct CA BAC process before executing this Jira ticket submission process'
                                exit()
                            elif cid_list.totalNumberOfRecords == 0 and len(configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec)) > 1:      
                                print 'No new issue (CID) is being detected compared between two latest snapshots. Hence no new ticket submission.\n' + str(configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec))
                                exit()
                                
                            print 'cid_list.mergedDefects ' + str(type(cid_list.mergedDefects)) + ' length is ' +str(len(cid_list.mergedDefects))
                            #print cid_list.mergedDefects[0]
                            print '\n'+'cid_list.mergedDefectIds type is ' + str(type(cid_list.mergedDefectIds)) + ' length is ' + str(len(cid_list.mergedDefectIds))
                            print cid_list.mergedDefectIds 
                                                    
                            for mdid in cid_list.mergedDefectIds:
                                print mdid.cid,mdid.mergeKey
                                #
                                #    DRILL DOWN Detection History
                                #
                                #
                                if list_md_detection_history == True :
                                    print '------------getMergedDefectDetectionHistory'
                                    defectDetectionHistory = defectServiceClient.client.service.getMergedDefectDetectionHistory(mdid, s.id)
                                    for mdh in defectDetectionHistory:
                                        print mdh.userName, mdh.defectDetection, mdh.detection, mdh.snapshotId, mdh.streams[0].name
                                #
                                #    DRILL DOWN Triage History
                                #
                                #
                                if list_md_history == True :
                                    print '------------getMergedDefectHistory'
                                    defectChanges = defectServiceClient.client.service.getMergedDefectHistory(mdid, s.id)
                                    for dc in defectChanges:
                                        #print getKeys(dc) 
                                        print dc.userModified,dc.dateModified,
                                        for sa in dc.affectedStreams:
                                            print sa.name
                                        for ca in dc.attributeChanges:
                                            if ca :
                                                for fc in ca:
                                                    print fc[0],'=',fc[1]#.fieldName,fc.oldValue,fc.newValue
                                        if hasattr(dc,'comments'):
                                            print 'comments = ',dc.comments
                                            #issue_dict[str(sd.cid).rstrip('L')] = {'Comments': sd.checkerName}
                                #
                                #    DRILL DOWN Stream Defects
                                #        optionally also get Triage History and Defect Instances
                                #
                                if list_stream_defects == True:
                                
                                    defect_dict = {} 
                                    
                                    print '------------getStreamDefects'
                                    streamDefectFilterDO = defectServiceClient.client.factory.create('streamDefectFilterSpecDataObj')
                                    #streamDefectFilterDO = defectServiceClient.client.factory.create('snapshotScopeDefectFilterSpecDataObj')
                                    
                                    streamDefectFilterDO.streamIdList=[s.id]
                                    streamDefectFilterDO.defectStateStartDate = '2010-09-05'
                                    streamDefectFilterDO.defectStateEndDate = '2020-10-05'       
                                    streamDefectFilterDO.includeDefectInstances = list_sd_defect_instances
                                    streamDefectFilterDO.includeHistory = list_sd_history 
                                    
                                    
                                    streamDefects = defectServiceClient.client.service.getStreamDefects(mdid, streamDefectFilterDO)
                                    for sd in streamDefects:
                                        print '<CID> ',sd.cid,' <Checker> ',sd.checkerName,' <Domain> ',sd.domain
                                        issue_dict[str(sd.cid).rstrip('L')] = {'CID': str(sd.cid).rstrip('L'), 'Checker': sd.checkerName, 'Domain': sd.domain}
                                        
                                        #print sd.id.defectTriageId, sd.id.defectTriageVerNum, sd.id.id,sd.id.verNum
                                        #for a in sd.defectStateAttributeValues:
                                            #print a.attributeDefinitionId.name,'=',a.attributeValueId.name
                                        #print sd.defectStateAttributeValues[0].attributeValueId.name, 'CID status value'
                                        issue_dict[str(sd.cid).rstrip('L')].update({'Status': sd.defectStateAttributeValues[0].attributeValueId.name})    
                                        if hasattr(sd,'history'):
                                            for dh in sd.history:
                                                print getKeys(dh)
                                                print dh.dateCreated,dh.userCreated
                                                for a in dh.defectStateAttributeValues:
                                                    print a.attributeDefinitionId.name,'=',a.attributeValueId.name
                                        if hasattr(sd,'defectInstances'):
                                           for di in sd.defectInstances:
                                                #print di.category.name,di.category.displayName
                                                #print di.checkerName
                                                #print di.component
                                                #print di.cwe
                                                #print di.domain
                                                #print di.extra
                                                try:
                                                    functionf = di.function.functionDisplayName
                                                except:
                                                    functionf = '-'
                                                
                                                print '<Function> ', functionf #, di.function.functionMangledName, di.function.functionMergeName
                                                print '<Path>', di.function.fileId.filePathname, di.function.fileId.contentsMD5 
                                                print '<ID> ', di.id.id
                                                print '<Impact>', di.impact.displayName,di.impact.name 
                                                issue_dict[str(sd.cid).rstrip('L')].update({'Function': str(functionf)})#+' '+di.function.functionMangledName+' '+di.function.functionMergeName})
                                                for ik in di.issueKinds:
                                                    print '<Issue Kind> ', ik.displayName, ik.name
                                                    issue_dict[str(sd.cid).rstrip('L')].update({'Issue Kind': str(ik.displayName)+' '+str(ik.name)})
                                                print '<Effect> ', di.localEffect
                                                print '<Description>', di.longDescription
                                                issue_dict[str(sd.cid).rstrip('L')].update({'Effect': str(di.localEffect), 'Description' : str(di.longDescription)})
                                                #print di.type.displayName, di.type.name
                                                for e in di.events:
                                                    if e.main:
                                                        #print e.main,e.polarity,e.eventKind, e.eventNumber, e.eventSet, e.eventTag 
                                                        print '<LineNumber> ', e.lineNumber
                                                        issue_dict[str(sd.cid).rstrip('L')].update({'LineNumber': str(e.lineNumber)})
                                                        #print '-FilePathName- ', e.fileId.filePathname, e.fileId.contentsMD5
                                                        #print '------------getFileContents'
                                                        v = defectServiceClient.client.service.getFileContents(s.id, di.function.fileId)
                                                        decompressedContent=zlib.decompress(bytes(bytearray(base64.b64decode(v['contents']))), 15+32)
                                                        #print 'decompressed:',len(decompressedContent) ,"bytes"
                                                        print '<Code_snippet> '
                                                        if len(decompressedContent) > 0:
                                                            ln=e.lineNumber-5
                                                            snippet=()
                                                            for l in decompressedContent.split('\n')[e.lineNumber-5:e.lineNumber+5]:
                                                                print ln,'>',l
                                                                snippet += ln,'>',l,'\r\n'
                                                                ln += 1
                                                            issue_dict[str(sd.cid).rstrip('L')].update({'Code_snippet': snippet})
                                                        print '<Defect Content End> '
                                                        
                ################################################################################
                print 'getSnapshotsForStream ' + str(type(configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec))) + '\n'
                print configServiceClient.client.service.getSnapshotsForStream(s.id, filterSpec)
                #---

print '\n'+'cid_list type is ' + str(type(cid_list))
#print len(cid_list)
print 'Total number of new record(s) '+ str(cid_list.totalNumberOfRecords)
print 'cid_list.mergedDefects ' + str(type(cid_list.mergedDefects)) + ' length is ' +str(len(cid_list.mergedDefects))
#print cid_list.mergedDefects[0]
#print '\n'+'cid_list.mergedDefectIds type is ' + str(type(cid_list.mergedDefectIds)) + ' length is ' + str(len(cid_list.mergedDefectIds))
print cid_list.mergedDefectIds
#print 'issue_duct check', issue_dict['10111']
#print 'issue_duct check', issue_dict['10002']
#print issue_dict.keys()

cid_sorted_list = sorted([int(i) for i in issue_dict.keys()])
#print cid_sorted_list

#for values in issue_dict.items():
#    print(values)
print 'time taken 2 is ', datetime.datetime.now() - begin
JIRA_URL = jserver
JIRA_username = juser  
JIRA_password = jpassword 
jira = JIRA(JIRA_URL, basic_auth=(JIRA_username, JIRA_password))

#jira_api_token='OaDsBFPmELMq9kwIcTCn53A2'
#jira = JIRA(basic_auth=(JIRA_username, jira_api_token), options={'server': jserver})

#issues = jira.search_issues("assignee=siguser")
#print issues

for cid in cid_sorted_list:
#   print issue_dict[value]['CID']
    print cid
    value = issue_dict.get(str(cid))
    #print value
    #print 'value Code_snippet is'
    #print type(value['Code_snippet'])
    #print value['Code_snippet']

    all_issue_dict = {
    'project': {'key': str(jkey)},
    'issuetype': {'name': 'Bug'},
    'labels': ['Coverity', 'CID:'+str(cid), 'Status:'+str(value['Status'])],
    'summary': (' <CID> '+value['CID']+' <Checker> '+value['Checker']+' <Function> '+value['Function'])[:255],
    'description': ' <Description> ' + value['Description'] 
    +'\r\n'+' <Effect> '+ value['Effect']
    +'\r\n'+' <Line_Number> '+ str(value['LineNumber'])
    +'\r\n'+' <Code_snippet> '+'\r\n'+ ' '.join(map(str, value['Code_snippet']))
    #'assignee': {'name': 'new_user'},
#    'report request type': 'Ad hoc',
#    'report frequency': 'Monthly',
#    'due date': '29/Oct/18'
    }
    #print type(''.join(map(str, value['Code_snippet'])))
#    for v in all_issue_dict.items():
#        print(v)
    #jira.create_issue(fields=all_issue_dict)
    #print all_issue_dict.get('project').get('key')
    
    try:
        jira.search_issues('project='+all_issue_dict.get('project').get('key'))
    except:
        print 'Jira project key ', str(jkey), 'may not existed, please create the project name and key in Jira before ticket submission.'
        exit()
    check_cid = jira.search_issues('project='+all_issue_dict.get('project').get('key')+' and labels=CID:'+str(cid))
    
    if not check_cid: 
        print 'Submit Jira ticket for CID ' + str(cid) + ' in Jira project with key ' + str(all_issue_dict.get('project').get('key'))
        issues = jira.issue(jira.create_issue(fields=all_issue_dict))
        jira.add_attachment(issue=issues, attachment=''+pdf)
        jira.add_attachment(issue=issues, attachment=''+csv)
    else:
        print 'CID ' + str(cid) + ' existed in Jira project with key ' + str(all_issue_dict.get('project').get('key'))  
    
    #issues = jira.issue(jira.create_issue(fields=all_issue_dict))
    #print(issues.fields.attachment) 

    #print all_issue_dict
    #break
print 'time taken after Jira execution is ', datetime.datetime.now() - begin
