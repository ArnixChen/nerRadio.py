#!/home/test/.local/venv_nerRadio/bin/python

import requests
import lxml
import bs4
import re
import demjson3 as demjson
import datetime
from tqdm import tqdm
import eyed3
import subprocess
import time
import argparse
import sys
import os
import signal
import send2trash

appVersion = "0.5 2021-10-11"
baseURL = "https://www.ner.gov.tw"
programWebXML = None
debugModeEnabled = False
currentDownloadFile = ""

def getWebData(url):
    headers = {
        'User-Agent':
        'Mozilla/5.0 (Windows NT 6.1; WOW64)\
              AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101\
              Safari/537.36',
    }

    try:
        #response = requests.get(url, headers=headers)
        response = requests.get(url)
        response.raise_for_status()  # P.23-8
    except Exception as err:
        print(f"擷取網路資料失敗: {err}")
        return "擷取網路資料失敗"

    return response


def getProgramInfo(programName):
    import json
    from urllib.parse import quote_plus as urlencode

    # 利用教育電台的「節目搜尋API」找出「節目專屬的JSON」資料
    beginURL = baseURL + "/api/programs?size=12&page=1&order=createdAt&desc=true&q="
    endURL = "&onShelf=true&overview=true"
    requestURL = beginURL + urlencode(programName) + endURL
    #print(f"requestURL = {requestURL}")
    if debugModeEnabled:
        print('Retrieve program-info by NER API: ', end='')
    webData = getWebData(requestURL)
    if debugModeEnabled:
        print('Done!')
    # print(webData.text);
    if len(webData.text) != 0:
        jsonData = json.loads(webData.text)
        if jsonData['count'] == 1:
            programID = jsonData['rows'][0]['_id']
            # print(f"programID = {programID}")
            programWebURL = f"{baseURL}/program/{programID}"
            # print(f"programWebURL = {programWebURL}")
            return {
                'programID': programID,
                'programWebURL': programWebURL,
            }
        else:
            return None
    else:
        return None


def getProgramWebXML(programName):
    programInfo = getProgramInfo(programName)
    if (programInfo == None):
        print(f"ERROR, No such program {programName}!")
        sys.exit(1)

    programWebURL = programInfo['programWebURL']
    print(f"programWebURL = {programWebURL}")
    if debugModeEnabled:
        print('Retrieve web-data from programWebURL: ', end='')
    webData = getWebData(programWebURL)
    if debugModeEnabled:
        print('Done!')

    #print(webData.text)
    #print()
    if debugModeEnabled:
        print(f'Convert web-data to XML with Beautiful-Soup: ', end='')
    objSoup = bs4.BeautifulSoup(webData.text, 'lxml')
    webJson = objSoup.find(id='preloaded-state').contents[0]
    webJson = webJson.removeprefix("window.__PRELOADED_STATE__=")
    # 為沒有加引號的 key 準備引號
    # 參考 https://stackoverflow.com/questions/34812821/bad-json-keys-are-not-quoted
    validJson = webJson.replace('!0', '0').replace('!1', '1')  # 移除有問題的驚嘆號開頭的值
    validJson = re.sub(r'(?<={|,)([a-zA-Z][a-zA-Z0-9]*)(?=:)', r'"\1"',
                       validJson)
    if debugModeEnabled:
        print('Done!')
    return validJson


def getProgramJsonData(programName, forceReload = False):
    global programWebXML
    if programWebXML == None or forceReload == True:
        programWebXML = getProgramWebXML(programName)
    if debugModeEnabled:
        print('Decode WebXML to JSON Object: ', end='')
    dataJson = demjson.decode(programWebXML)
    if debugModeEnabled:
        print('Done!')
    return dataJson


def getProgramShowDays(programName):
    objJson = getProgramJsonData(programName)
    showSchedule = objJson['reducers']['program']['getItem']['time']
    weekDict = {'一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '日':7}
    rawShowDays = showSchedule['text'].replace('週', '').replace('周', '')
    rawShowDays = rawShowDays.replace('每', '')
    rawShowDays = rawShowDays.replace('至', '-')
    rawShowDays = rawShowDays.replace('~', '-')
    rawShowDays = rawShowDays.replace('、', ',')
    rawShowDays = rawShowDays.replace('一-二','1,2')
    rawShowDays = rawShowDays.replace('二-三','2,3')
    rawShowDays = rawShowDays.replace('三-四','3,4')
    rawShowDays = rawShowDays.replace('四-五','4,5')
    rawShowDays = rawShowDays.replace('五-六','5,6')
    rawShowDays = rawShowDays.replace('六-日','6,7')
    rawShowDays = rawShowDays.replace('五-日','5,6,7')
    rawShowDays = rawShowDays.replace('一-三-三','1,2,3')
    rawShowDays = rawShowDays.replace('一-三','1,2,3')
    rawShowDays = rawShowDays.replace('一-四','1,2,3,4')
    rawShowDays = rawShowDays.replace('一-五','1,2,3,4,5')
    rawShowDays = rawShowDays.replace('一-六','1,2,3,4,6')
    rawShowDays = rawShowDays.replace('一-七','1,2,3,4,5,6,7')
    showDays = re.split(',', rawShowDays)
    showDays = list(map(lambda x:  weekDict[x] if x in weekDict.keys() else int(x), showDays))
    return showDays


def getJsonEntryOfDay(programName, dayObj, forceReload = False): 
    objJson = getProgramJsonData(programName, forceReload)
    dayString = f"{dayObj['year']}-{dayObj['month']}-{dayObj['day']}"
    showList = objJson['reducers']['programList']['data']
    if debugModeEnabled:
        print(f'Search show\'s JsonEntry of day {dayString}: ', end='')
    for show in showList:
        date = datetime.date.fromtimestamp(show['date'])
        #print(str(date.year) + "." + str(date.month) + str(date.day))
        showDayString = date.strftime("%Y-%m-%d")
        # https://www.ner.gov.tw/api/audio/613bff966a9c870008f8dd68

        if showDayString == dayString:
            if debugModeEnabled:
                print('Found!')
            return show
    if debugModeEnabled:
        print('Not found!')
    return None


def getAudioURLOfJsonObj(showJson):
    #print(showJson)
    if showJson == None:
        return None
    else:
        dayString = datetime.date.fromtimestamp(showJson['date'])
        programName = showJson['program']['name']
        if 'audio' in showJson:
            if showJson['audio'] != None:
                if 'channel' in showJson['audio']:
                    audioURL = baseURL + '/api/audio/' + showJson['audio']['channel']['_id'] + ".mp3"
                    return audioURL
            else:
                if debugModeEnabled:
                    print("AudioURL is EMPTY!")
                print(f"ERROR, [{programName}, {dayString}] audio file is not yet for download!")
                return None
        else:
            print(f"ERROR, [{programName}, {dayString}] audio file is not yet for download!")
            return None


def getAudioFileOfJsonObj(showJson, programName, dayObj, outputFolder):
    dayString = f"{dayObj['year']}.{dayObj['month']}{dayObj['day']}"
    audioURL = getAudioURLOfJsonObj(showJson)

    if audioURL == None:
        return None
    else:
        print(dayString + ' ' + showJson['title'])
        print("audioURL = " + audioURL)
        webData = requests.get(audioURL, stream=True)
        totalSizeInBytes = int(webData.headers.get('content-length', 0))
        blockSize = 1024  #1K bytes
        fileName = outputFolder + dayString + '.' + programName + '.mp3'
        global currentDownloadFile
        currentDownloadFile = fileName
        progressBar = tqdm(total=totalSizeInBytes, unit='iB', unit_scale=True)
        with open(fileName, 'wb') as fileObj:
            for packet in webData.iter_content(blockSize):
                progressBar.update(len(packet))
                fileObj.write(packet)
        progressBar.close()
        if totalSizeInBytes != 0 and progressBar.n != totalSizeInBytes:
            print("ERROR, something went wrong!")
        else:
            return fileName

def updateID3Tag(showJson, fileName, dayObj):
    dayString = f"{dayObj['year']}.{dayObj['month']}{dayObj['day']}"
    audioFile = eyed3.load(fileName)
    tag = audioFile.initTag()
    tag.title = dayString + ' ' + showJson['title']
    tag.comment = showJson['introduction']
    tag.album = showJson['program']['name']
    tag.album_artist = showJson['editor']
    tag.artist = " "
    if len(showJson['guests']) > 0:
        for guest in showJson['guests']:
            if guest['name'] != None:
                tag.artist = tag.artist + guest['name']
            if guest['unit'] != None:
                tag.artist = tag.artist + guest['unit'] + ' '
    tag.audio_file_url = getAudioURLOfJsonObj(showJson)
    #tag.release_date = showJson['audio']['audio']['createdAt']
    tag.save()

def checkOutputFolder(outputFolder=""):
    homeFolder = os.getenv('HOME') if os.name == 'posix' else os.path.expanduser('~/Documents')
    if outputFolder == "" or outputFolder == None:
        outputFolder = homeFolder + '/Radio/' + programName
        if not os.path.exists(homeFolder + '/Radio'):
            os.mkdir(homeFolder + '/Radio')
        if not os.path.exists(homeFolder + '/Radio/' + programName):
            os.mkdir(homeFolder + '/Radio/' + programName)
    if not os.path.exists(outputFolder):
        os.mkdir(outputFolder)

    if outputFolder[-1] != '/':
        outputFolder = outputFolder + '/'
    return outputFolder

def getAudioOfDay(programName, dayObj, outputFolder=""):
    homeFolder = os.getenv('HOME') if os.name == 'posix' else os.path.expanduser('~/Documents')
    outputFolder = checkOutputFolder(outputFolder)

    dayString = f"{dayObj['year']}-{dayObj['month']}-{dayObj['day']}"
    targetDatetime = datetime.datetime.fromisoformat(dayString)
    todayDatetime = datetime.datetime.today()
    showJson = None
    waitUntilReady = True
    while waitUntilReady == True:
        if todayDatetime < targetDatetime:
            if waitUntilReady == True:
                # sleep until targetDatetime arrive
                print(f"ERROR, [{programName}, {dayString}] is not yet come!")
                delta = targetDatetime - todayDatetime
                time.sleep(delta.seconds+2)
        else:
            showJson = getJsonEntryOfDay(programName, dayObj, True)
            if showJson == None:
                print(f'ERROR, [{programName}] is not available on {dayString}!')
                return None

            #print(f'{dayString} showJson={type(showJson)}')
            audioURL = getAudioURLOfJsonObj(showJson)
            if audioURL != None:
                break
            else:
                #print(f'{dayString} audioURL={audioURL}')
                print(f'Retry getAudioURLOfJsonObj() for {dayString} 10 minutes later.')
                time.sleep(600)

    fileName = getAudioFileOfJsonObj(showJson, programName, dayObj, outputFolder)

    if fileName == None:
        return None
    else:
        print(f'audioFile = {fileName}')
        updateID3Tag(showJson, fileName, dayObj)
        #os.execl("/usr/bin/mpg123", "/home/arnix/bin/complete.mp3")
        completeMP3 = homeFolder + "/bin/complete.mp3"
        if os.path.exists(completeMP3):
            if os.path.exists('/usr/bin/mpg123'):
                subprocess.run(["/usr/bin/mpg123", "-q", completeMP3])
        return 0


#getProgramInfo('愛的加油站')
#getProgramInfo('教育行動家(上)')
#programWebURL = getProgramInfo("愛的加油站")['programWebURL']
#print(f"programWebURL = {programWebURL}")

#getProgramWebXML("愛的加油站")
#getAudioOfDay("愛的加油站", "2021-08-07")
#getAudioOfDay("愛的加油站", "2021-09-11")


def getDayObjFromString(dayString):
    if re.match(r'[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}', dayString):
        year = dayString.split('-')[0]
        month = dayString.split('-')[1]
        day = dayString.split('-')[2]
    elif re.match(r'[0-9]{4}\.[0-9]{4}', dayString):
        year = dayString.split('.')[0]
        month = dayString.split('.')[1][0:2]
        day = dayString.split('.')[1][2:4]
    elif re.match(r'[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}', dayString):
        year = dayString.split('/')[0]
        month = dayString.split('/')[1]
        day = dayString.split('/')[2]
    elif re.match(r'[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,2}', dayString):
        year = dayString.split('.')[0]
        month = dayString.split('.')[1]
        day = dayString.split('.')[2]
    return {'year': year, 'month': month, 'day': day}

def generateRequiredModulesList():
    with open(__file__, 'r') as fileObj:
        for line in fileObj:
            #print(line, end='')
            pattern = r'^([ \t]*)(import|from) ([a-zA-Z0-9]+)'
            result = re.search(pattern, line)
            if result != None:
                print(result.group(3))

def signalHandlerCtrlC(sig, frame):
    global currentDownloadFile
    print('You pressed Ctrl+C!')
    if os.path.exists(currentDownloadFile):
        send2trash.send2trash(currentDownloadFile)
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signalHandlerCtrlC)
    #normalProcess()
    #generateRequiredModulesList()
    parser = argparse.ArgumentParser(description=f"Script for Downloading radio programs of National Education Radio. rev. {appVersion}")
    parser.add_argument('-n',
        dest='programName',
        nargs= 1,
        #action='extend',
        help='Program Name to be download.'
        )
    parser.add_argument('-d',
        dest='date',
        nargs= 1,
        action='store',
        help='Date to be download.'
        )
    parser.add_argument('-o',
        dest='outputFolder',
        nargs=1,
        action='store',
        help='Specify output folder.'
        )
    parser.add_argument('-g',
        dest='getShow',
        action='store_true',
        help='Do radio program download.'
        )
    parser.add_argument('-f',
        dest='fillUp',
        action='store_true',
        help='Fill up all shows that have not been downloaded.'
        )
    parser.add_argument('-l',
        dest='listModules',
        action='store_true',
        help='List required modules.'
        )
    parser.add_argument('-j',
        dest='getJsonEntryOfDay',
        action='store_true',
        help='Get json entry of show with day.'
        )
    parser.add_argument('-e',
        dest='debugModeEnabled',
        action='store_true',
        help='Enable debug mode.'
        )
        
    #parser.print_help()
    params = sys.argv[1:]
    if len(sys.argv) == 1:
        params.append('-h')
    paramList = vars(parser.parse_args(params))
    #global debugModeEnabled
    debugModeEnabled = paramList['debugModeEnabled']
    
    #print(paramList)
    if paramList['listModules'] == True:
      generateRequiredModulesList()
      sys.exit(0)
    elif paramList['getShow'] == True:
        date = None
        if paramList['date'] == None:
            date = datetime.date.today().isoformat()
        else:
            date = paramList['date'][0]
        dayObj = getDayObjFromString(date)
        if (paramList['programName'] == None):
            print("ERROR, Program name is missing!")
            sys.exit(1)
        programName = paramList['programName'][0]
        #print(programName)
        if (paramList['outputFolder'] != None):
            outputFolder = paramList['outputFolder'][0]
        else:
            outputFolder = None
        outputFolder = checkOutputFolder(outputFolder)
        result = getAudioOfDay(programName, dayObj, outputFolder)
        if result == None:
            sys.exit(1)
        else:
            sys.exit(0)
    elif paramList['getJsonEntryOfDay'] == True:
        date = None
        if paramList['date'] == None:
            date = datetime.date.today().isoformat()
        else:
            date = paramList['date'][0]
        dayObj = getDayObjFromString(date)
        if (paramList['programName'] == None):
            print("ERROR, Program name is missing!")
            sys.exit(1)
        programName = paramList['programName'][0]
        #print(programName)
        if date == datetime.date.today().isoformat():
            dayString = f"{dayObj['year']}-{dayObj['month']}-{dayObj['day']}"
            programWebXML = getProgramWebXML(programName)
            if debugModeEnabled:
                print('Decode WebXML to JSON Object: ', end='')
            result = demjson.decode(programWebXML)
            if result == None:
                print(f'ERROR, No json entry for program {programName}')
                sys.exit(1)
            else:
                print(result)
                sys.exit(0)
        else:
            result = getJsonEntryOfDay(programName, dayObj)
            if result == None:
                print(f'ERROR, No json entry for day {date}')
                sys.exit(1)
            else:
                print(result)
                sys.exit(0)
    elif paramList['fillUp'] == True:
        if (paramList['programName'] == None):
            print("ERROR, Program name is missing!")
            sys.exit(1)
        programName = paramList['programName'][0]

        if (paramList['outputFolder'] != None):
            outputFolder = paramList['outputFolder'][0]
        else:
            outputFolder = None
        outputFolder = checkOutputFolder(outputFolder)

        showDays = getProgramShowDays(programName)        
        print(f'showDays = {showDays}')
    
        today = datetime.date.today()
        for diff in list(range(60, 0, -1)):
            delta = datetime.timedelta(days = diff)
            tgtDay = today - delta
            if tgtDay.isoweekday() in showDays:
                #print(tgtDay.isoformat())
                dayObj = getDayObjFromString(tgtDay.isoformat())
                dayString = f"{dayObj['year']}.{dayObj['month']}{dayObj['day']}"
                fileName = outputFolder + dayString + '.' + programName + '.mp3'
                if not os.path.exists(fileName):
                #print(fileName)
                #print(tgtDay.isoformat() + ' ', end='')
                    result = getAudioOfDay(programName, dayObj)         
                else:
                    print(f'File {fileName} exists!')

        sys.exit(0)


