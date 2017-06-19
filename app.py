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
from Store import dataStore

app = Flask(__name__)
app.secret_key = 'render_templateqweaqdfsafASDAS,smaCount=smaCount)'
store= dataStore()
@app.route('/')
def main():
    session['smaCount']=0
    store=dataStore()
    store.dataList=[]
    store.graphs=dict()
    store.symbolList=[]
    store.optionList=[]
    return render_template('index.html')

@app.route('/rule')
def rule():
    print
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
    smas=request.form.getlist('sma[]')
    print smas
    graphs=store.graphs
    dataList=store.dataList
    graphData=graphs.get("data")
    for sma in smas:
        counter=0
        for data in dataList:
            data[store.symbolList[counter]+"_SMA_"+sma]=pd.rolling_mean(data.Close,int(sma))
            graphData.append(go.Scatter(
                    x=data.index,  # Can use the pandas data structures directly
                    y=data[store.symbolList[counter]+"_SMA_"+sma],
                    name=store.symbolList[counter]+"_SMA_"+sma
                )
           )
            store.optionList.append(store.symbolList[counter]+"_SMA_"+sma)
            counter=counter+1
    graphs["data"]=graphData
    store.graphs=graphs
    store.dataList=dataList
    graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON


@app.route('/plotBoll',methods=['POST'])
def plotBoll():
    graphs=store.graphs
    dataList=store.dataList
    graphData=graphs.get("data")
    counter=0
    for data in dataList:
        data[store.symbolList[counter]+'_Bol_upper'] = pd.rolling_mean(data.Close, window=20) + 2* pd.rolling_std(data.Close, 20, min_periods=20)
        data[store.symbolList[counter]+'_Bol_lower'] = pd.rolling_mean(data.Close, window=20) - 2* pd.rolling_std(data.Close, 20, min_periods=20)
        graphData.append(go.Scatter(
                x=data.index,  # Can use the pandas data structures directly
                y=data[store.symbolList[counter]+"_Bol_upper"],
                name=store.symbolList[counter]+"_Bol_upper"
            )
        )
        store.optionList.append(store.symbolList[counter]+"_Bol_upper")
        graphData.append(go.Scatter(
                x=data.index,  # Can use the pandas data structures directly
                y=data[store.symbolList[counter]+"_Bol_lower"],
                name=store.symbolList[counter]+"_Bol_lower"
            )
        )
        store.optionList.append( store.symbolList[counter]+"_Bol_lower")
        counter=counter+1
    graphs["data"]=graphData
    store.graphs=graphs
    store.dataList=dataList
    graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON

@app.route('/getSymbols',methods=['POST'])
def getSymbols():
    _symbols=request.form['symbols']
    _from=datetime.datetime.strptime(request.form['from'], '%m/%d/%Y').strftime('%Y-%m-%d')
    _to=datetime.datetime.strptime(request.form['to'], '%m/%d/%Y').strftime('%Y-%m-%d')
    symbolList= _symbols.split(',');
    store.symbolList=symbolList
    dataList=[];
    graphs=dict(
        data=[],
        layout=dict(
            title=_symbols,
            yaxis=dict(
                title="Time"
            ),
            xaxis=dict(
                title="Close"
            )
        )
    )
    graphData=graphs.get("data")
    for symbol in symbolList:
        store.optionList.append(symbol+"_Close")
        data =pdr.get_data_yahoo(symbol,start=_from, end=_to)
        dataList.append(data)
        graphData.append(go.Scatter(
                    x=data.index,  # Can use the pandas data structures directly
                    y=data.Close,
                    name=symbol
                )
           )
    graphs["data"]=graphData

  
    #session['data']=dataList
    store.dataList=dataList
    store.graphs=graphs
    graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON
    
def executeRule(ruleL,ruleRule,ruleSignal,ruleR,data):
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
    data.to_csv('dataout2.csv')
    return totalProfit, maxProfit, maxLoss, maxDrawdown, peakdays,buyCount,sellCount

@app.route('/runRules',methods=['POST'])
def runRules():
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
    return render_template('result.html',totalProfit=results[0],profit=results[1],loss=results[2],
    drawdown=results[3],peak=results[4],buy=results[5],sell=results[6])   


if __name__=='__main__':
    app.run()