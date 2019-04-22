import datetime
import json
import urllib
import numpy as np
import fix_yahoo_finance
import pandas as pd
import plotly
import plotly.graph_objs as go
from flask import Flask, jsonify, render_template, request,session
from pandas_datareader import data as pdr
from datetime import timedelta
from Store import dataStore
from flask_session import Session


app = Flask(__name__)
app.secret_key = 'render_templateqweaqdfsafASDAS,smaCount=smaCount)'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=5)

# The maximum number of items the session stores
# before it starts deleting some, default 500
app.config['SESSION_FILE_THRESHOLD'] = 100
Session(app)

@app.route('/')
def main():
    session['smaCount']=0
    session['smas']=[]
    session['hasBolinger']=False
    session['store']=dataStore()
    return render_template('index.html')

@app.route('/rule')
def rule():
    store=session['store']
    return render_template('rule.html',options=store.optionList)

@app.route('/sma')
def sma():
    if 'smaCount' in session:
          smaCount = session['smaCount']
    else:
         smaCount = 0
    smaCount=smaCount+1;
    session['smaCount']=smaCount
    return render_template('sma.html',smaCount=smaCount)

@app.route('/plotSMAs',methods=['POST'])
def plotSMAs():
    store=session['store']
    smas=request.form.getlist('sma[]')
    session['smas']=smas
    dataList=store.dataList
    for sma in smas:
        counter=0
        for data in dataList:
            data[store.symbolList[counter]+"_SMA_"+sma]=pd.rolling_mean(data.Close,int(sma))
            store.optionList.append(store.symbolList[counter]+"_SMA_"+sma)
            counter=counter+1
    store.dataList=dataList
    graphs=plotGraphs(store)
    graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
    session['store']=store
    return graphJSON


@app.route('/plotBoll',methods=['POST'])
def plotBoll():
    store=session['store']
    print(session['store'])
    dataList=store.dataList
    counter=0
    session['hasBolinger'] = True
    for data in dataList:
        data[store.symbolList[counter]+'_Bol_upper'] = pd.rolling_mean(data.Close, window=20) + 2* pd.rolling_std(data.Close, 20, min_periods=20)
        data[store.symbolList[counter]+'_Bol_lower'] = pd.rolling_mean(data.Close, window=20) - 2* pd.rolling_std(data.Close, 20, min_periods=20)
        store.optionList.append(store.symbolList[counter]+"_Bol_upper")
        store.optionList.append( store.symbolList[counter]+"_Bol_lower")
        counter=counter+1
    store.dataList=dataList
    graphs=plotGraphs(store)
    graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
    session['store']=store
    return graphJSON

@app.route('/getSymbols',methods=['POST'])
def getSymbols():
    session['smaCount']=0
    store=dataStore()
    store.reset()
    _symbols=request.form['symbols']
    _from=datetime.datetime.strptime(request.form['from'], '%m/%d/%Y').strftime('%Y-%m-%d')
    _to=datetime.datetime.strptime(request.form['to'], '%m/%d/%Y').strftime('%Y-%m-%d')
    symbolList= _symbols.split(',');
    store.symbolList=symbolList
    dataList=[];

    for symbol in symbolList:
        store.optionList.append(symbol+"_Close")
        data =pdr.get_data_yahoo(symbol,start=_from, end=_to)
        dataList.append(data)
    #session['data']=dataList
    store.dataList=dataList
    graphs=plotGraphs(store)
    graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
    #
    session['store']=store
    return graphJSON
def getGraphDict(_symbols):
    return dict(
        data=[],
        layout=dict(
            title=_symbols,
            yaxis=dict(
                title="Close"
            ),
            xaxis=dict(
                title="Time"
            )
        )
    )

def executeRule(ruleL,ruleRule,ruleSignal,ruleR,data):
    store=session['store']
    data['signal']=""
    data['price']=0.0
    data.fillna(0)
    lastSignal=''
    totalProfit=0
    maxProfit=0
    maxLoss=0
    maxDrawdown=0
    peakdays=0
    buyCount=0
    sellCount=0
    for i in range(1,len(data)):
        #print i
        for iterator in range(len(ruleL)):
            if ruleRule[iterator]=='goes above':
                if (data.signal[i]=='') & (data[ruleL[iterator]][i-1]>data[ruleR[iterator]][i-1]) & (lastSignal!=ruleSignal[iterator]):
                    data['signal'][i]= ruleSignal[iterator]
                    lastSignal=ruleSignal[iterator]
            else:
                if (data.signal[i]=='') & (data[ruleL[iterator]][i-1]<data[ruleR[iterator]][i-1]) & (lastSignal!=ruleSignal[iterator]):
                    data['signal'][i]= ruleSignal[iterator]
                    lastSignal=ruleSignal[iterator]
        if data['signal'][i]=='SELL':
                sellCount+=1
                data['price'][i]=data[store.symbolList[0]+'_Open'][i]
        elif data['signal'][i]=='BUY':
            buyCount+=1
            data['price'][i]=-1*data[store.symbolList[0]+'_Open'][i]
        else:
            data['price'][i]=0
        totalProfit+=data['price'][i]
        if totalProfit>maxProfit:
            maxProfit=totalProfit
            peakdays=0
        else:
            peakdays+=1
            if maxDrawdown>totalProfit:
                maxDrawdown=totalProfit
        if totalProfit<maxLoss:
            maxLoss=totalProfit
    return totalProfit, maxProfit, maxLoss, maxDrawdown, peakdays,buyCount,sellCount

@app.route('/runRules',methods=['POST'])
def runRules():
    store=session['store']
    ruleL=request.form.getlist('ruleL[]')
    ruleRule=request.form.getlist('ruleRule[]')
    ruleSignal=request.form.getlist('ruleSignal[]')
    ruleR=request.form.getlist('ruleR[]')
    dataList=store.dataList
    dataCount=len(dataList)
    resultData= pd.DataFrame()
    counter=0
    print dataCount
    for data in dataList:
        data.rename(columns={'Open': store.symbolList[counter]+'_Open', 'High': store.symbolList[counter]+'_High',
        'Low':store.symbolList[counter]+'_Low','Close':store.symbolList[counter]+'_Close','Adj Close':store.symbolList[counter]+'_Adj Close',
        'Volume':store.symbolList[counter]+'_Volume'}, inplace=True)
        resultData=pd.concat([resultData, data], axis=1, join_axes=[data.index])
        counter=counter+1
    #result = pd.concat([df1, df4], axis=1, join_axes=[df1.index])
    results=executeRule(ruleL,ruleRule,ruleSignal,ruleR,resultData)
    session['store']=store
    return render_template('result.html',totalProfit=results[0],profit=results[1],loss=results[2],
    drawdown=results[3],peak=results[4],buy=results[5],sell=results[6])

def appendGraphData(graphData,data,column,isClose):
    if isClose == True:
        graphData.append(go.Scatter(
            x=data.index,  # Can use the pandas data structures directly
            y=data.Close,
            name=column
            )
        )
    else:
        graphData.append(go.Scatter(
            x=data.index,  # Can use the pandas data structures directly
            y=data[column],
            name=column
            )
        )

def plotGraphs(store):
     graphs = getGraphDict(','.join(store.symbolList))
     graphData=graphs.get("data")
     counter=0
     for data in store.dataList:
         appendGraphData(graphData,data,store.symbolList[counter],True)
         if session['hasBolinger']:
            appendGraphData(graphData,data,store.symbolList[counter]+"_Bol_upper",False)
            appendGraphData(graphData,data,store.symbolList[counter]+"_Bol_lower",False)

         if 'smas' in session:
             for sma in session['smas']:
                 appendGraphData(graphData,data,store.symbolList[counter]+"_SMA_"+sma,False)
         counter=counter+1
     graphs["data"]=graphData
     return graphs


if __name__=='__main__':
    app.run()
