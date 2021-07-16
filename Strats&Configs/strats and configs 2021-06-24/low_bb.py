# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from functools import reduce
from typing import Dict, List

from pandas import DataFrame
from skopt.space import Dimension, Integer, Real

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, CategoricalParameter, IntParameter
from freqtrade.strategy import RealParameter


class Low_BB(IStrategy):
    """

    author@: Thorsten

    works on new objectify branch!

    idea:
        buy after crossing .98 * lower_bb and sell if trailing stop loss is hit
    """
    bb_factor = RealParameter(0.01, 1, default=0.89416, space='buy')
    buy_trigger = CategoricalParameter(['bb_lower1',
                                        'bb_lower2',
                                        'bb_lower3'], default="bb_lower1", space="buy")

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    """minimal_roi = {
        "0": 0.9,
        "1": 0.05,
        "10": 0.04,
        "15": 0.5
    }"""

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    #stoploss = -0.015

    # Optimal ticker interval for the strategy
    #ticker_interval = '1m'

    # Optional order type mapping
    order_types = {
        'buy': 'limit',
        'sell': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': False
    }

    # Optional time in force for orders
    order_time_in_force = {
        'buy': 'gtc',
        'sell': 'gtc',
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ##################################################################################
        # buy and sell indicators

        bollinger1 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=1)
        dataframe['bb_lowerband1'] = bollinger1['lower']
        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband2'] = bollinger2['lower']
        bollinger3 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=3)
        dataframe['bb_lowerband3'] = bollinger3['lower']

        #dataframe['ema50'] = ta.EMA(dataframe, timeperiod=20)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        """dataframe.loc[
            (
                #(dataframe['close'] > dataframe['ema50']) &
                qtpylib.crossed_below(dataframe['close'], 0.98 * dataframe['bb_lowerband'])
                #(dataframe['close'] <= 0.98 * dataframe['bb_lowerband'])

            )
            ,
            'buy'] = 1"""
        conditions = []
        if self.buy_trigger.value == 'bb_lower1':
            conditions = [qtpylib.crossed_below(dataframe['close'], self.bb_factor.value * dataframe['bb_lowerband1'])]
        if self.buy_trigger.value == 'bb_lower2':
            conditions = [qtpylib.crossed_below(dataframe['close'], self.bb_factor.value * dataframe['bb_lowerband2'])]
        if self.buy_trigger.value == 'bb_lower3':
            conditions = [qtpylib.crossed_below(dataframe['close'], self.bb_factor.value * dataframe['bb_lowerband3'])]
        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (),
            'sell'] = 0
        return dataframe

    @staticmethod
    def generate_roi_table(params: Dict) -> Dict[int, float]:
        """
        Generate the ROI table that will be used by Hyperopt
        """
        roi_table = {}
        roi_table[0] = params['roi_p1'] + params['roi_p2'] + params['roi_p3']
        roi_table[params['roi_t3']] = params['roi_p1'] + params['roi_p2']
        roi_table[params['roi_t3'] + params['roi_t2']] = params['roi_p1']
        roi_table[params['roi_t3'] + params['roi_t2'] + params['roi_t1']] = 0

        return roi_table

    @staticmethod
    def stoploss_space() -> List[Dimension]:
        """
        Stoploss Value to search
        """
        return [
            Real(-0.5, -0.015, name='stoploss'),
        ]

    @staticmethod
    def roi_space() -> List[Dimension]:
        """
        Values to search for each ROI steps
        """
        return [
            Integer(10, 120, name='roi_t1'),
            Integer(10, 60, name='roi_t2'),
            Integer(10, 40, name='roi_t3'),
            Real(0.01, 0.04, name='roi_p1'),
            Real(0.01, 0.07, name='roi_p2'),
            Real(0.01, 0.20, name='roi_p3'),
        ]
