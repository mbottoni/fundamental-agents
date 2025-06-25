class ValuationAgent:
    def __init__(self, risk_free_rate=0.04, market_return=0.08, perpetual_growth_rate=0.025):
        self.risk_free_rate = risk_free_rate
        self.market_return = market_return
        self.perpetual_growth_rate = perpetual_growth_rate

    def _calculate_wacc(self, raw_data):
        try:
            profile = raw_data.get('profile', {})
            financials = raw_data.get('financials', {})
            
            beta = profile.get('beta')
            market_cap = profile.get('mktCap')
            
            balance_sheet = financials.get('balance_sheet', [{}])[0]
            income_statement = financials.get('income_statement', [{}])[0]

            total_debt = balance_sheet.get('totalDebt')
            interest_expense = income_statement.get('interestExpense')
            income_before_tax = income_statement.get('incomeBeforeTax')
            
            if not all([beta, market_cap, total_debt, interest_expense, income_before_tax]):
                return None

            # Cost of Equity (CAPM)
            cost_of_equity = self.risk_free_rate + beta * (self.market_return - self.risk_free_rate)
            
            # Cost of Debt
            effective_tax_rate = income_statement.get('incomeTaxExpense') / income_before_tax if income_before_tax else 0.21
            cost_of_debt = interest_expense / total_debt if total_debt else 0
            after_tax_cost_of_debt = cost_of_debt * (1 - effective_tax_rate)

            # WACC Calculation
            equity_value = market_cap
            debt_value = total_debt
            total_capital = equity_value + debt_value

            wacc = ((equity_value / total_capital) * cost_of_equity) + ((debt_value / total_capital) * after_tax_cost_of_debt)
            return wacc
        except (TypeError, ZeroDivisionError, IndexError):
            return None

    def _project_free_cash_flow(self, cash_flow_data):
        # Simplified: Use the most recent FCF and a simple growth rate
        try:
            latest_fcf = cash_flow_data[0].get('freeCashFlow')
            if not latest_fcf:
                return None, None

            # Calculate historical growth rate (simplified)
            fcf_history = [cf.get('freeCashFlow', 0) for cf in cash_flow_data[:5]]
            growth_rates = [(fcf_history[i] - fcf_history[i+1]) / fcf_history[i+1] for i in range(len(fcf_history)-1) if fcf_history[i+1] != 0]
            avg_growth_rate = sum(growth_rates) / len(growth_rates) if growth_rates else 0.05
            
            projected_fcf = []
            for i in range(1, 6): # Project for 5 years
                projected_fcf.append(latest_fcf * ((1 + avg_growth_rate) ** i))
            
            return projected_fcf, latest_fcf
        except (IndexError, TypeError, ZeroDivisionError):
            return None, None

    def run(self, raw_data: dict):
        wacc = self._calculate_wacc(raw_data)
        if wacc is None:
            return {"dcf_intrinsic_value_per_share": None, "error": "Could not calculate WACC."}

        cash_flow_statement = raw_data.get('financials', {}).get('cash_flow', [])
        projected_fcf, latest_fcf = self._project_free_cash_flow(cash_flow_statement)
        if projected_fcf is None:
            return {"dcf_intrinsic_value_per_share": None, "error": "Could not project Free Cash Flow."}

        # Discount the projected FCF
        dcf_sum = sum([fcf / ((1 + wacc) ** (i + 1)) for i, fcf in enumerate(projected_fcf)])

        # Calculate Terminal Value
        terminal_value = (projected_fcf[-1] * (1 + self.perpetual_growth_rate)) / (wacc - self.perpetual_growth_rate)
        discounted_terminal_value = terminal_value / ((1 + wacc) ** len(projected_fcf))
        
        # Calculate Intrinsic Value
        intrinsic_value = dcf_sum + discounted_terminal_value
        
        shares_outstanding = raw_data.get('profile', {}).get('sharesOutstanding')
        if not shares_outstanding:
            return {"dcf_intrinsic_value_per_share": None, "error": "Shares outstanding not available."}
            
        intrinsic_value_per_share = intrinsic_value / shares_outstanding
        
        return {
            "dcf_intrinsic_value_per_share": intrinsic_value_per_share,
            "wacc": wacc,
            "latest_fcf": latest_fcf
        } 