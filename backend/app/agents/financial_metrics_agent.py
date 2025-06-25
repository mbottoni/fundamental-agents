import pandas as pd

class FinancialMetricsAgent:
    def calculate_pe_ratio(self, price_data, earnings_data):
        """
        Calculate the Price-to-Earnings (P/E) ratio.
        Requires latest stock price and earnings per share.
        """
        try:
            latest_price = price_data[0]['close']
            # Assuming annual earnings data is provided
            latest_eps = earnings_data[0]['eps']
            if latest_eps != 0:
                return latest_price / latest_eps
            return None
        except (IndexError, TypeError, KeyError):
            return None

    def calculate_d_e_ratio(self, balance_sheet_data):
        """
        Calculate the Debt-to-Equity (D/E) ratio.
        """
        try:
            # Assuming annual balance sheet data
            latest_balance_sheet = balance_sheet_data[0]
            total_debt = latest_balance_sheet.get('totalDebt')
            total_equity = latest_balance_sheet.get('totalEquity')
            if total_debt is not None and total_equity is not None and total_equity != 0:
                return total_debt / total_equity
            return None
        except (IndexError, TypeError):
            return None
    
    def run(self, raw_data: dict):
        """
        Calculates all financial metrics.
        """
        financials = raw_data.get('financials', {})
        prices = raw_data.get('prices', [])
        
        income_statement = financials.get('income_statement', [])
        balance_sheet = financials.get('balance_sheet', [])

        pe_ratio = self.calculate_pe_ratio(prices, income_statement)
        de_ratio = self.calculate_d_e_ratio(balance_sheet)

        return {
            "pe_ratio": pe_ratio,
            "de_ratio": de_ratio,
        }
