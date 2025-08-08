trading_site/
├── app.py
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
└── data/
    └── calculator.py
    Flask==2.3.3
yfinance==0.2.22
pandas==2.1.1
numpy==1.25.2
requests==2.31.0
python-dateutil==2.8.2
APScheduler==3.10.4
from flask import Flask, render_template, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from data.calculator import TradingCalculator

app = Flask(__name__)

# Inicializar calculadora
calc = TradingCalculator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/current_price')
def get_current_price():
    try:
        ticker = yf.Ticker("ABEV3.SA")
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            current_price = float(data['Close'].iloc[-1])
            return jsonify({
                'success': True,
                'price': round(current_price, 2),
                'timestamp': datetime.now().isoformat()
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/alerts')
def get_alerts():
    try:
        alerts = calc.check_alerts()
        return jsonify({'success': True, 'alerts': alerts})
    except Exception as e:
        return jsonResponse({'success': False, 'error': str(e)})

@app.route('/api/probabilities')
def get_probabilities():
    try:
        probabilities = calc.calculate_range_probabilities()
        return jsonify({'success': True, 'probabilities': probabilities})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reversal_probabilities')
def get_reversal_probabilities():
    try:
        reversals = calc.calculate_reversal_probabilities()
        return jsonify({'success': True, 'reversals': reversals})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import calendar

class TradingCalculator:
    def __init__(self):
        self.ticker = "ABEV3.SA"
        self.data = self.load_historical_data()
        
    def load_historical_data(self):
        """Carrega dados históricos de 5 anos"""
        try:
            stock = yf.Ticker(self.ticker)
            data = stock.history(period="5y")
            return data
        except Exception as e:
            print(f"Erro ao carregar dados: {e}")
            return pd.DataFrame()
    
    def get_current_price(self):
        """Obtém preço atual"""
        try:
            stock = yf.Ticker(self.ticker)
            current = stock.history(period="1d")
            return float(current['Close'].iloc[-1])
        except:
            return 0
    
    def get_option_cycle_dates(self):
        """Calcula datas dos ciclos de opções"""
        today = datetime.now().date()
        current_month = today.month
        current_year = today.year
        
        # Terceira segunda-feira do mês (vencimento de opções)
        def third_monday(year, month):
            first_day = date(year, month, 1)
            first_monday = first_day + timedelta(days=(7 - first_day.weekday()) % 7)
            return first_monday + timedelta(days=14)
        
        # Próximos vencimentos
        monthly_exp = third_monday(current_year, current_month)
        if monthly_exp < today:
            if current_month == 12:
                monthly_exp = third_monday(current_year + 1, 1)
            else:
                monthly_exp = third_monday(current_year, current_month + 1)
        
        # Bimestral (próximo após mensal)
        next_month = monthly_exp.month + 1 if monthly_exp.month < 12 else 1
        next_year = monthly_exp.year if monthly_exp.month < 12 else monthly_exp.year + 1
        bimonthly_exp = third_monday(next_year, next_month)
        
        return {
            'monthly': monthly_exp,
            'bimonthly': bimonthly_exp,
            'weekly': today + timedelta(days=(4 - today.weekday()) % 7)
        }
    
    def calculate_historical_ranges(self, period_days):
        """Calcula ranges históricos para um período"""
        if self.data.empty:
            return {}
        
        ranges = []
        for i in range(len(self.data) - period_days):
            period_data = self.data.iloc[i:i+period_days]
            if len(period_data) >= period_days:
                open_price = period_data['Open'].iloc[0]
                close_price = period_data['Close'].iloc[-1]
                variation = abs(close_price - open_price) / open_price
                ranges.append(variation)
        
        ranges = np.array(ranges)
        
        return {
            'percentile_60': np.percentile(ranges, 60),
            'percentile_70': np.percentile(ranges, 70),
            'percentile_75': np.percentile(ranges, 75),
            'percentile_80': np.percentile(ranges, 80)
        }
    
    def calculate_range_probabilities(self):
        """Calcula probabilidades de ranges"""
        current_price = self.get_current_price()
        cycles = self.get_option_cycle_dates()
        
        # Calcular para diferentes períodos
        weekly_ranges = self.calculate_historical_ranges(5)  # 5 dias úteis
        monthly_ranges = self.calculate_historical_ranges(21)  # ~21 dias úteis/mês
        bimonthly_ranges = self.calculate_historical_ranges(42)  # ~42 dias úteis
        
        def create_range_info(ranges, current_price):
            return {
                '60%': {
                    'min': round(current_price * (1 - ranges['percentile_60']), 2),
                    'max': round(current_price * (1 + ranges['percentile_60']), 2)
                },
                '70%': {
                    'min': round(current_price * (1 - ranges['percentile_70']), 2),
                    'max': round(current_price * (1 + ranges['percentile_70']), 2)
                },
                '75%': {
                    'min': round(current_price * (1 - ranges['percentile_75']), 2),
                    'max': round(current_price * (1 + ranges['percentile_75']), 2)
                },
                '80%': {
                    'min': round(current_price * (1 - ranges['percentile_80']), 2),
                    'max': round(current_price * (1 + ranges['percentile_80']), 2)
                }
            }
        
        return {
            'current_price': current_price,
            'weekly': {
                'end_date': cycles['weekly'].strftime('%d/%m/%Y'),
                'days_remaining': (cycles['weekly'] - datetime.now().date()).days,
                'ranges': create_range_info(weekly_ranges, current_price)
            },
            'monthly': {
                'end_date': cycles['monthly'].strftime('%d/%m/%Y'),
                'days_remaining': (cycles['monthly'] - datetime.now().date()).days,
                'ranges': create_range_info(monthly_ranges, current_price)
            },
            'bimonthly': {
                'end_date': cycles['bimonthly'].strftime('%d/%m/%Y'),
                'days_remaining': (cycles['bimonthly'] - datetime.now().date()).days,
                'ranges': create_range_info(bimonthly_ranges, current_price)
            }
        }
    
    def calculate_reversal_probabilities(self):
        """Calcula probabilidades de reversão"""
        if self.data.empty:
            return {}
        
        current_price = self.get_current_price()
        cycles = self.get_option_cycle_dates()
        
        # Simular probabilidades baseadas em dados históricos
        # (implementação simplificada para demonstração)
        
        def simulate_reversals(period_days):
            reversals = {20: 0, 30: 0, 40: 0, 50: 0}
            total_samples = 0
            
            for i in range(len(self.data) - period_days):
                period_data = self.data.iloc[i:i+period_days]
                if len(period_data) >= period_days:
                    max_price = period_data['High'].max()
                    min_price = period_data['Low'].min()
                    open_price = period_data['Open'].iloc[0]
                    close_price = period_data['Close'].iloc[-1]
                    
                    # Verificar reversões
                    price_range = max_price - min_price
                    for threshold in [20, 30, 40, 50]:
                        target_reversal = price_range * (threshold / 100)
                        if abs(close_price - open_price) >= target_reversal:
                            reversals[threshold] += 1
                    total_samples += 1
            
            # Converter para percentuais
            if total_samples > 0:
                for key in reversals:
                    reversals[key] = round((reversals[key] / total_samples) * 100, 1)
            
            return reversals
        
        return {
            'weekly': {
                'days_remaining': (cycles['weekly'] - datetime.now().date()).days,
                'probabilities': simulate_reversals(5)
            },
            'monthly': {
                'days_remaining': (cycles['monthly'] - datetime.now().date()).days,
                'probabilities': simulate_reversals(21)
            },
            'bimonthly': {
                'days_remaining': (cycles['bimonthly'] - datetime.now().date()).days,
                'probabilities': simulate_reversals(42)
            }
        }
    
    def check_alerts(self):
        """Verifica condições de alerta"""
        alerts = []
        current_price = self.get_current_price()
        
        if self.data.empty:
            return alerts
        
        # Calcular médias históricas de variação
        recent_data = self.data.tail(252)  # Último ano
        daily_ranges = recent_data['High'] - recent_data['Low']
        avg_daily_range = daily_ranges.mean()
        
        # Verificar se atingiu níveis de alerta
        today_high = recent_data['High'].iloc[-1]
        today_low = recent_data['Low'].iloc[-1]
        today_range = today_high - today_low
        
        if today_range >= avg_daily_range * 0.8:
            cycles = self.get_option_cycle_dates()
            reversals = self.calculate_reversal_probabilities()
            
            alerts.append({
                'type': 'range_alert',
                'message': f'ABEV3 atingiu {round((today_range/avg_daily_range)*100, 1)}% da variação média',
                'weekly_days': (cycles['weekly'] - datetime.now().date()).days,
                'monthly_days': (cycles['monthly'] - datetime.now().date()).days,
                'bimonthly_days': (cycles['bimonthly'] - datetime.now().date()).days,
                'reversals': reversals
            })
        
        return alerts
        <!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor ABEV3 - Análise de Probabilidades</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container-fluid">
        <!-- Header -->
        <nav class="navbar navbar-dark bg-dark mb-4">
            <div class="container">
                <span class="navbar-brand h1">📊 Monitor ABEV3</span>
                <span class="text-light" id="current-time"></span>
            </div>
        </nav>

        <!-- Preço Atual -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card bg-primary text-white">
                    <div class="card-body text-center">
                        <h2 class="card-title">ABEV3.SA</h2>
                        <h1 class="display-4" id="current-price">R$ --,--</h1>
                        <small id="last-update">Última atualização: --</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Alertas -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h4>🚨 Alertas em Tempo Real</h4>
                    </div>
                    <div class="card-body" id="alerts-container">
                        <p class="text-muted">Nenhum alerta ativo no momento.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Probabilidades de Range -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h4>📈 Probabilidades de Range no Fechamento</h4>
                    </div>
                    <div class="card-body">
                        <div class="row" id="range-probabilities">
                            <!-- Será preenchido via JavaScript -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Probabilidades de Reversão -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h4>🔄 Probabilidades de Reversão</h4>
                    </div>
                    <div class="card-body">
                        <div class="row" id="reversal-probabilities">
                            <!-- Será preenchido via JavaScript -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
</body>
</html>
body {
    background-color: #f8f9fa;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.card {
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s;
}

.card:hover {
    transform: translateY(-2px);
}

.alert-card {
    border-left: 5px solid #dc3545;
    background: linear-gradient(135deg, #fff5f5 0%, #ffffff 100%);
}

.probability-card {
    text-align: center;
    padding: 1rem;
    margin-bottom: 1rem;
    border-radius: 8px;
    background: linear-gradient(135deg, #e3f2fd 0%, #ffffff 100%);
}

.probability-60 { border-left: 4px solid #28a745; }
.probability-70 { border-left: 4px solid #17a2b8; }
.probability-75 { border-left: 4px solid #ffc107; }
.probability-80 { border-left: 4px solid #dc3545; }

.reversal-card {
    background: linear-gradient(135deg, #f3e5f5 0%, #ffffff 100%);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
}

.price-display {
    font-size: 2.5rem;
    font-weight: bold;
    color: #007bff;
}

.period-title {
    color: #495057;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.9rem;
    letter-spacing: 1px;
}

.countdown {
    background: #6c757d;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.8rem;
}

.status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 5px;
}

.status-online { background-color: #28a745; }
.status-offline { background-color: #dc3545; }
.status-loading { background-color: #ffc107; }

@media (max-width: 768px) {
    .display-4 {
        font-size: 2rem;
    }
    
    .card-body {
        padding: 1rem;
    }
}

.fade-in {
    animation: fadeIn 0.5s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.pulse {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.02); }
    100% { transform: scale(1); }
}
class TradingMonitor {
    constructor() {
        this.isOnline = false;
        this.updateInterval = 5000; // 5 segundos
        this.init();
    }

    init() {
        this.updateCurrentTime();
        this.startUpdates();
        setInterval(() => this.updateCurrentTime(), 1000);
    }

    updateCurrentTime() {
        const now = new Date();
        document.getElementById('current-time').textContent = 
            now.toLocaleString('pt-BR');
    }

    async fetchData(endpoint) {
        try {
            const response = await fetch(`/api/${endpoint}`);
            const data = await response.json();
            return data.success ? data : null;
        } catch (error) {
            console.error(`Erro ao buscar ${endpoint}:`, error);
            return null;
        }
    }

    async updateCurrentPrice() {
        const data = await this.fetchData('current_price');
        if (data) {
            document.getElementById('current-price').textContent = 
                `R$ ${data.price.toFixed(2)}`;
            document.getElementById('last-update').textContent = 
                `Última atualização: ${new Date(data.timestamp).toLocaleTimeString('pt-BR')}`;
            this.setOnlineStatus(true);
        } else {
            this.setOnlineStatus(false);
        }
    }

    async updateAlerts() {
        const data = await this.fetchData('alerts');
        const container = document.getElementById('alerts-container');
        
        if (data && data.alerts.length > 0) {
            container.innerHTML = '';
            data.alerts.forEach(alert => {
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-warning alert-card fade-in';
                alertDiv.innerHTML = this.createAlertHTML(alert);
                container.appendChild(alertDiv);
            });
        } else {
            container.innerHTML = '<p class="text-muted">Nenhum alerta ativo no momento.</p>';
        }
    }

    createAlertHTML(alert) {
        return `
            <h5>🚨 ${alert.message}</h5>
            <div class="row mt-3">
                <div class="col-md-4">
                    <strong>Semanal:</strong> ${alert.weekly_days} dias restantes<br>
                    Reversões: 20%→${alert.reversals.weekly.probabilities[20]}%, 
                    30%→${alert.reversals.weekly.probabilities[30]}%
                </div>
                <div class="col-md-4">
                    <strong>Mensal:</strong> ${alert.monthly_days} dias restantes<br>
                    Reversões: 20%→${alert.reversals.monthly.probabilities[20]}%, 
                    30%→${alert.reversals.monthly.probabilities[30]}%
                </div>
                <div class="col-md-4">
                    <strong>Bimestral:</strong> ${alert.bimonthly_days} dias restantes<br>
                    Reversões: 20%→${alert.reversals.bimonthly.probabilities[20]}%, 
                    30%→${alert.reversals.bimonthly.probabilities[30]}%
                </div>
            </div>
        `;
    }

    async updateRangeProbabilities() {
        const data = await this.fetchData('probabilities');
        const container = document.getElementById('range-probabilities');
        
        if (data) {
            container.innerHTML = '';
            
            ['weekly', 'monthly', 'bimonthly'].forEach(period => {
                const periodData = data.probabilities[period];
                const periodDiv = document.createElement('div');
                periodDiv.className = 'col-md-4 mb-3';
                periodDiv.innerHTML = this.createRangeHTML(period, periodData);
                container.appendChild(periodDiv);
            });
        }
    }

    createRangeHTML(period, data) {
        const periodNames = {
            weekly: 'Semanal',
            monthly: 'Mensal',
            bimonthly: 'Bimestral'
        };

        let rangesHTML = '';
        Object.entries(data.ranges).forEach(([prob, range]) => {
            rangesHTML += `
                <div class="probability-card probability-${prob.replace('%', '')}">
                    <strong>${prob}</strong><br>
                    R$ ${range.min} - R$ ${range.max}
                </div>
            `;
        });

        return `
            <div class="card">
                <div class="card-body">
                    <h5 class="period-title">${periodNames[period]}</h5>
                    <p class="small text-muted">
                        Termina em: ${data.end_date}<br>
                        <span class="countdown">${data.days_remaining} dias restantes</span>
                    </p>
                    ${rangesHTML}
                </div>
            </div>
        `;
    }

    async updateReversalProbabilities() {
        const data = await this.fetchData('reversal_probabilities');
        const container = document.getElementById('reversal-probabilities');
        
        if (data) {
            container.innerHTML = '';
            
            ['weekly', 'monthly', 'bimonthly'].forEach(period => {
                const periodData = data.reversals[period];
                const periodDiv = document.createElement('div');
                periodDiv.className = 'col-md-4 mb-3';
                periodDiv.innerHTML = this.createReversalHTML(period, periodData);
                container.appendChild(periodDiv);
            });
        }
    }

    createReversalHTML(period, data) {
        const periodNames = {
            weekly: 'Semanal',
            monthly: 'Mensal',  
            bimonthly: 'Bimestral'
        };

        let probsHTML = '';
        Object.entries(data.probabilities).forEach(([threshold, probability]) => {
            probsHTML += `
                <div class="d-flex justify-content-between mb-2">
                    <span>${threshold}% reversão:</span>
                    <strong>${probability}%</strong>
                </div>
            `;
        });

        return `
            <div class="card">
                <div class="card-body reversal-card">
                    <h5 class="period-title">${periodNames[period]}</h5>
                    <p class="small text-muted">
                        <span class="countdown">${data.days_remaining} dias restantes</span>
                    </p>
                    ${probsHTML}
                </div>
            </div>
        `;
    }

    setOnlineStatus(online) {
        this.isOnline = online;
        const indicator = document.querySelector('.status-indicator') || 
                        this.createStatusIndicator();
        
        indicator.className = `status-indicator ${online ? 'status-online' : 'status-offline'}`;
    }

    createStatusIndicator() {
        const indicator = document.createElement('span');
        indicator.className = 'status-indicator';
        document.querySelector('.navbar-brand').appendChild(indicator);
        return indicator;
    }

    async startUpdates() {
        // Primeira atualização imediata
        await this.updateAll();
        
        // Atualizações periódicas
        setInterval(() => this.updateAll(), this.updateInterval);
    }

    async updateAll() {
        await Promise.all([
            this.updateCurrentPrice(),
            this.updateAlerts(),
            this.updateRangeProbabilities(),
            this.updateReversalProbabilities()
        ]);
    }
}

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    new TradingMonitor();
});
