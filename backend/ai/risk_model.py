import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
FEATURES=["expense_to_income_ratio","savings_months","debt_to_income_ratio","family_size","employment","inflation_exposure"]
def build_model():
    rng=np.random.default_rng(42); n=1000
    income=rng.uniform(8000,100000,n); ratio=rng.uniform(.35,1.7,n); savings=rng.uniform(0,8,n); debt=rng.uniform(0,2,n); family=rng.integers(1,8,n); employed=rng.integers(0,2,n); exposure=rng.uniform(0,1,n)
    X=np.column_stack([ratio,savings,debt,family,employed,exposure]); y=((ratio>1.0)|((savings<1)&(debt>.5))|(employed==0)).astype(int)
    model=LogisticRegression(max_iter=500,random_state=42).fit(X[:800],y[:800]); pred=model.predict(X[800:])
    metrics={"accuracy":round(float(accuracy_score(y[800:],pred)),3),"precision":round(float(precision_score(y[800:],pred,zero_division=0)),3),"recall":round(float(recall_score(y[800:],pred,zero_division=0)),3),"f1":round(float(f1_score(y[800:],pred,zero_division=0)),3),"confusion_matrix":confusion_matrix(y[800:],pred).tolist(),"feature_names":FEATURES}
    return model,metrics
MODEL,METRICS=build_model()
def predict_risk(income, expense, savings, debt, family, employed, exposure=0):
    safe_income=max(income,1); values=[[expense/safe_income, savings/max(expense,1), debt/safe_income, family, int(employed), exposure]]
    return float(MODEL.predict_proba(values)[0][1])
