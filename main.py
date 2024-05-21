import requests
import json
import re
import time
import os
import platform
import getpass
import random


def DESencrypt(key, password): # key from base64
    from Crypto.Cipher import DES
    from Crypto.Util.Padding import pad
    import base64
    key = base64.b64decode(key)
    password = password.encode()
    cipher = DES.new(key, DES.MODE_ECB) 
    password = pad(password, DES.block_size)
    encText = cipher.encrypt(password)
    return base64.b64encode(encText).decode()


def getHeaders(token):
    # ticket = ""
    # NL = 'useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict'
#     ticket = execjs.compile("""const NL = 'useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict';
# function ticket(e=21){
#     let t = ""
#       , r = crypto.getRandomValues(new Uint8Array(e));
#     for (; e--; )
#         t += NL[r[e] & 63];
#     return t
# }
# """).call("ticket") # from vendor-Dano3rOA.js
    
    # headers = {
    #     'Skl-Ticket': ticket, 
    #     'X-Auth-Token': token,
    # }
    # 不加ticket头也能过
    headers = {
        'X-Auth-Token': token, 
    }

    return headers


def login(username, password):

    ul = str(len(username))
    pl = str(len(password))

    r = requests.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=")
    casurl = r.json()['url'] # CASurl
    r = requests.get(casurl, allow_redirects=False)
    ssourl = r.headers['Location'] # SSO login url

    # start login 
    session = requests.Session()
    r = session.get(ssourl)
    # directly use regular expression to find out "cropto" and "execution"
    key = re.findall(r'>.+<', re.findall(r'<p id="login-croypto">.+</p>', r.text)[0])[0][1 : -1]
    execution = re.findall(r'>.+<', re.findall(r'<p id="login-page-flowkey">.+</p>', r.text)[0])[0][1 : -1]


    data = {
        "username": username,
        "type": "UsernamePassword", # <p id="current-login-type"> CONST
        "_eventId": "submit",
        "geolocation": "",
        "execution": execution, # <p id="login-page-flowkey"> 
        "captcha_code": "",
        "croypto": key, # <p id="login-croypto">
        "password": DESencrypt(key, password), 
    }
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", 
                            "Content-Type": "application/x-www-form-urlencoded"})

    r = session.post(ssourl, data=data, allow_redirects=False) # it is necessary to disallow redirects
    location = r.headers["Location"]
    r = session.get(location)
    # r.url -> like https://skl.hduhelp.com/#?token=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx&t=timestamp
    token = re.findall(r'token=.+&', r.url)[0][6:-1]
    headers = getHeaders(token)
    r = requests.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=", headers=headers)
    print("登录成功！你好，"+json.loads(r.text)["userName"])
    return token


def getWeek(token):
    # 一个根据startTime获取周数的api
    headers = getHeaders(token)

    r = requests.get("https://skl.hdu.edu.cn/api/course?startTime=2024-04-08", headers=headers)
    return json.loads(r.text)["week"]


def exam(token, week, mode, delay):
    startTime = time.time()
    if mode == '0':
        print("开始自测")
    elif mode == '1':
        print("开始考试")
    url = f"https://skl.hdu.edu.cn/api/paper/new?type={mode}&week={week}&startTime=" + str(int(startTime*1000))
    headers = getHeaders(token)
    # 考试需要手机的UA
    headers["User-Agent"] = "Mozilla/5.0 (Linux; Android 4.2.1; M040 Build/JOP40D) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.59 Mobile Safari/537.36"
    r = requests.get(url, headers=headers) # 获取题目
    paper = json.loads(r.text)
    ans = getAnswer(paper)
    paperId = ans["paperId"]

    print("等待提交中...请不要关闭终端...")
    time.sleep(delay)
    r = requests.post("https://skl.hdu.edu.cn/api/paper/save", json=ans, headers=getHeaders(token)) # 不知道为什么这里json=json.dumps(ans)会400
    print("提交成功！")
    time.sleep(0.5)
    url = f"https://skl.hdu.edu.cn/api/paper/detail?paperId={paperId}"
    r = requests.get(url, headers=getHeaders(token))
    print("本次成绩:", json.loads(r.text)["mark"])


def getAnswer(paper):
    print("开始查找答案...")

    with open("cet-4.json", "r", encoding="utf-8") as f:
        bank = json.loads(f.read())

    ans = {
        "paperId": paper["paperId"],
        "type": paper["type"],
        "list": []
    }

    notFound = 0
    questionNum = 0
    for question in paper["list"]:
        questionNum += 1
        dic = {
            "input": "A", # 默认选项
            "paperDetailId": question["paperDetailId"]
        }

        title = question["title"].replace(" ", "").replace(".", "").split("，")[0]
        found = False
        if re.search(r'[a-zA-z]', title) != None: # english to chinese
            for obj in bank:
                if title == obj["Word"]:
                    for k in ["answerA", "answerB", "answerC", "answerD"]:
                        question[k] = question[k].replace(" ", "").replace(".", "")
                        if question[k] in obj["Mean"]:
                            dic["input"] = k[-1]
                            found = True
                            break
                if found:
                    break
            else:
                print(f"第{questionNum}题查找失败！cet-{question['cet']} e2c")
                notFound += 1
        else: # chinese to english
            for obj in bank:
                if title in obj["Mean"]:
                    for k in ["answerA", "answerB", "answerC", "answerD"]:
                        question[k] = question[k].replace(" ", "").replace(".", "")
                        if question[k] == obj["Word"]:
                            dic["input"] = k[-1]
                            found = True
                            break
                if found:
                    break
            else:
                print(f"第{questionNum}题查找失败！cet-{question['cet']} c2e")
                notFound += 1

        ans["list"].append(dic)

    print("not found:", notFound)
    print("查找结束！")
    return ans


def check(paper):
    # 测试用的验证程序

    ans = getAnswer(paper)       
    # print(ans)
    right = 0
    for i in range(100):
        if ans["list"][i]["input"] == paper["list"][i]["answer"]:
            right += 1
        else:
            print(f"第{i+1}题错误！")
    print("right:", right)
    

def makeWordbank(token):
    # 爬取自测列表 构建题库 待开发
    headers=getHeaders(token)
    url = f'https://skl.hdu.edu.cn/api/paper/list?type=0&week={6}&schoolYear={"2023-2024"}&semester={"2"}'
    r = requests.get(url, headers=headers)
    li = json.loads(r.text)
    with open("wordBank.json", "r", encoding='utf-8') as f:
        wordList = json.load(f)
    for i in li:
        paperId = i["paperId"]
        url = f'https://skl.hdu.edu.cn/api/paper/detail?paperId={paperId}'
        r = requests.get(url,) # 测试发现不需要认证身份
        paper = json.loads(r.text)
        for question in paper["list"]:
            title = question["title"].replace(" ", "").replace(".", "")
            if str(question["answer"]) in "ABCD":
                answer = question["answer"+question["answer"]].replace(" ", "").replace(".", "")
                word = {
                    title:answer
                }
                if word not in wordList:
                    wordList.append(word)
    with open("wordBank.json", "w", encoding='utf-8') as f:
        f.write(json.dumps(wordList))


def main():
    while True:
        try:
            un = input("请输入学号: ")
            pd = getpass.getpass("请输入密码(输入时不会显示任何字符): ")
            print("登录中...请稍后...")
            command = 'cls' if platform.system().lower() == 'windows' else 'clear'  
            os.system(command)  
            token = login(un, pd)
            break
        except KeyboardInterrupt:
            exit()
        except RuntimeError:
            print("请检查本次输入")
            print("账号:", un)
            print("密码:", pd)
            print("用户名或密码错误！(输入错误多次会导致禁止登录一段时间，请访问 https://skl.hduhelp.com/#/english/list 查看是否可以正常登录)")
            print("按下ctrl+C退出")
        except:
            raise
        
    # try:
    #     week = getWeek(token)
    #     print(f"本周是第{week}周")
    # except:
    #     print("自动获取周数失败！")
    #     week = 0 # 周数不准确影响不大

    while True:
        try:
            mode = input("请选择模式自测(0)/考试(1): ")
            assert mode == '0' or mode == '1'
            delay = int(input("输入做题时间(s)建议范围300-480或者0(不用等待自测用): ")) # 450 = 7min30s
            if delay < 300 or delay > 480:
                if not(mode == '0' and delay == 0):
                    print("数据不在建议范围内，已帮您设置成450")
                    delay = 450
            print(f"需要等待时间为{delay//60}分{delay%60}秒")  
            break
        except KeyboardInterrupt:
            exit()
        except AssertionError:
            print("输入数据有误！请重新输入！")
        except:
            raise
    exam(token, 1, mode, delay)


if __name__ == "__main__":
    main()