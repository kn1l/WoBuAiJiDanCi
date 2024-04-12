import requests
import json
import execjs
import re
import time
import os
import platform

def getHeaders(token):
    ticket = execjs.compile("""const NL = 'useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict';
function ticket(e=21){
    let t = ""
      , r = crypto.getRandomValues(new Uint8Array(e));
    for (; e--; )
        t += NL[r[e] & 63];
    return t
}
""").call("ticket") # from vendor-Dano3rOA.js
    
    headers = {
        'Skl-Ticket': ticket, # 实际测试发现skl-ticket好像没什么用(?
        'X-Auth-Token': token,
    }

    return headers


def login(username, password):

    s = requests.Session()

    ul = str(len(username))
    pl = str(len(password))

    r = requests.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=")
    csaurl = r.json()['url'] # CASurl

    r = s.get(csaurl) # 跳转CAS获取sessionid
    i = re.search(r'"LT-.+"', r.text).span()
    lt = r.text[i[0]+1:i[1]-1] # login token
    i = re.search(r'name="execution" value=".+"', r.text).span()
    execution = r.text[i[0]+24:i[1]-1]

    with open("./des.js", "r", encoding="utf-8") as f:
        context = execjs.compile(f.read())
        rsa = context.call("strEnc", username+password+lt , '1' , '2' , '3')

    data = {
        "rsa": rsa,
        "ul": ul,
        "pl": pl,
        "lt": lt,
        "execution": execution,
        "_eventId": "submit",
    }
    r = s.post(csaurl, data=data, allow_redirects=False) # 禁止重定向是必要的
    castgc = s.cookies["CASTGC"] # 没研究过有什么用
    location = r.headers["Location"]
    r = s.get(location, allow_redirects=False)
    location = r.headers["Location"]
    token = re.findall(r'token=.+&', location)[0][6:-1]
    headers = getHeaders(token)
    r = requests.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=", headers=headers)
    print("登录成功！你好，"+json.loads(r.text)["userName"])
    return token


def getWeek(token):
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
    

def main():
    while True:
        try:
            un = input("请输入学号: ")
            pd = input("请输入密码: ")
            print("登录中...请稍后...")
            command = 'cls' if platform.system().lower() == 'windows' else 'clear'  
            os.system(command)  
            token = login(un, pd)
            break
        except:
            print("用户名或密码错误！(如果尝试多次请访问 https://skl.hduhelp.com/#/english/list 查看是否可以正常登录)")
        
    try:
        week = getWeek(token)
        print(f"本周是第{week}周")
    except:
        print("自动获取周数失败！")
        week = 0 # 周数不准确影响不大

    while True:
        try:
            mode = input("请选择模式自测(0)/考试(1): ")
            assert mode == '0' or mode == '1'
            delay = int(input("输入做题时间(s)建议范围300-480或者0(不用等待自测用): ")) # 450 = 7min30s
            if delay < 300 or delay > 480 or delay != 0:
                print("数据不在建议范围内，已帮您设置成450")
                delay = 450
            print(f"需要等待时间为{delay//60}分{delay%60}秒")  
            break
        except:
            print("输入数据有误！请重新输入！")
    exam(token, week, mode, delay)


if __name__ == "__main__":
    main()