from backend.ai.risk_model import predict_risk
def test_risk_is_probability(): assert 0<=predict_risk(30000,28000,1000,20000,5,False,.3)<=1
