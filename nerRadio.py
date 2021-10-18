#!/usr/bin/python3

import requests
import bs4
import re
import demjson
import datetime
from tqdm import tqdm
import eyed3

baseURL = "https://www.ner.gov.tw"


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

    webData = getWebData(requestURL)
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

    programWebURL = getProgramInfo(programName)['programWebURL']
    #print(f"programWebURL = {programWebURL}")
    webData = getWebData(programWebURL)
    #print(webData.text)
    #print()
    objSoup = bs4.BeautifulSoup(webData.text, 'lxml')
    webJson = objSoup.find(id='preloaded-state').contents[0]
    webJson = webJson.removeprefix("window.__PRELOADED_STATE__=")
    # 為沒有加引號的 key 準備引號
    # 參考 https://stackoverflow.com/questions/34812821/bad-json-keys-are-not-quoted
    validJson = webJson.replace('!0', '0').replace('!1', '1')  # 移除有問題的驚嘆號開頭的值
    validJson = re.sub(r'(?<={|,)([a-zA-Z][a-zA-Z0-9]*)(?=:)', r'"\1"',
                       validJson)
    return validJson


def getJsonEntryOfDay(programName, dayString):
    objJson = demjson.decode(getProgramWebXML(programName))
    showList = objJson['reducers']['programList']['data']
    for show in showList:
        date = datetime.date.fromtimestamp(show['date'])
        #print(str(date.year) + "." + str(date.month) + str(date.day))
        showDayString = date.strftime("%Y-%m-%d")
        # https://www.ner.gov.tw/api/audio/613bff966a9c870008f8dd68

        if showDayString == dayString:
            return show


def getAudioURLOfJsonObj(showJson):
    if 'audio' in showJson:
        audioURL = baseURL + '/api/audio/' + showJson['audio']['channel'][
            '_id'] + ".mp3"
        print("audioURL = " + audioURL)
        return audioURL
    else:
        return None


def getAudioFileOfJsonObj(showJson, programName, dayString):
    audioURL = getAudioURLOfJsonObj(showJson)
    if audioURL != None:
        webData = requests.get(audioURL, stream=True)
        totalSizeInBytes = int(webData.headers.get('content-length', 0))
        blockSize = 1024  #1K bytes
        fileName = dayString + '.' + programName + '.mp3'
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
    else:
        print(
            f"ERROR, audio file not yet ready for {programName}, {dayString}")
        return None


def updateID3Tag(showJson, fileName):
    audioFile = eyed3.load(fileName)
    tag = audioFile.initTag()
    tag.title = showJson['title']
    tag.comment = showJson['introduction']
    tag.album = showJson['program']['name']
    tag.album_artist = showJson['editor']
    tag.artist = showJson['guests'][0]['name'] + showJson['guests'][0]['unit']
    tag.audio_file_url = getAudioURLOfJsonObj(showJson)
    #tag.release_date = showJson['audio']['audio']['createdAt']
    tag.save()

def getAudioOfDay(programName, dayString):
    showJson = getJsonEntryOfDay(programName, dayString)
    fileName = getAudioFileOfJsonObj(showJson, programName, dayString)
    updateID3Tag(showJson, fileName)

#getProgramInfo('愛的加油站')
#getProgramInfo('教育行動家(上)')
#programWebURL = getProgramInfo("愛的加油站")['programWebURL']
#print(f"programWebURL = {programWebURL}")

#getProgramWebXML("愛的加油站")
#getAudioOfDay("愛的加油站", "2021-08-07")
#getAudioOfDay("愛的加油站", "2021-09-11")

if __name__ == '__main__':
    import sys
    if (len(sys.argv) != 3):
        print("pRadioDownload.py -- Download NER's program audio'");
        print("syntax: pRadioDownload.py <programName> <Date>")
        print("    ex. pRadioDownload.py '愛的加油站' '2021-09-11'\n")
    else:
        programName = sys.argv[1]
        dayString = sys.argv[2]
        getAudioOfDay(programName, dayString)


