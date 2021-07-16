# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from functools import reduce
from typing import Dict, Any, Callable, List
import numpy as np
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy
from freqtrade.strategy import CategoricalParameter, IntParameter, RealParameter
from skopt.space import Dimension, Integer, Real

import freqtrade.vendor.qtpylib.indicators as qtpylib


class BBRSI_ETH_OPT(IStrategy):
    """
    Hyperopt
    """

    buy_rsi = IntParameter(5, 50, default=40, space="buy")
    buy_rsi_enabled = CategoricalParameter([True, False], default=False, space="buy")
    buy_trigger =CategoricalParameter(['bb_lower1',
                                        'bb_lower2',
                                        'bb_lower3'], default="bb_lower3", space="buy")

    sell_rsi = IntParameter(50, 100, default=53, space="sell")
    sell_rsi_enabled = CategoricalParameter([True, False], default=False, space="sell")
    sell_trigger= CategoricalParameter([#'sell-bb_lower2',
                                        'sell-bb_lower1',
                                        'sell-bb_middle1',
                                        'sell-bb_upper1'], default='sell-bb_lower1', space='sell')
    stoploss = RealParameter(-0.02, -0.5, default=-0.307, space="stoploss")
    """
    # Minimal ROI designed for the strategy
    minimal_roi = {
        "0": 0.07916501011003861,
        "28": 0.035159901969879184,
        "83": 0.016727420189894475,
        "131": 0
    }
    """
    # Optimal stoploss designed for the strategy
    #stoploss = -0.4275704128061333

    # Optimal ticker interval for the strategy
    #ticker_interval = '1h'

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
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Raw data from the exchange and parsed by parse_ticker_dataframe()
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """

        # Momentum Indicator
        # -----------------------------------
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)

        # Overlap Studies
        # ------------------------------------

        # Bollinger bands
        bollinger3 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=3)
        dataframe['bb_lowerband3'] = bollinger3['lower']
        dataframe['bb_middleband3'] = bollinger3['mid']
        dataframe['bb_upperband3'] = bollinger3['upper']

        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband2'] = bollinger2['lower']
        dataframe['bb_middleband2'] = bollinger2['mid']
        dataframe['bb_upperband2'] = bollinger2['upper']

        bollinger1 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=1)
        dataframe['bb_lowerband1'] = bollinger1['lower']
        dataframe['bb_middleband1'] = bollinger1['mid']
        dataframe['bb_upperband1'] = bollinger1['upper']

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Buy strategy Hyperopt will build and use
        """
        conditions = []
        # GUARDS AND TRENDS
        if self.buy_rsi_enabled.value:
            conditions.append(dataframe['rsi'] > self.buy_rsi.value)

        # TRIGGERS

        if self.buy_trigger.value == 'bb_lower1':
            conditions.append(dataframe['close'] < dataframe['bb_lowerband1'])
        if self.buy_trigger.value == 'bb_lower2':
            conditions.append(dataframe['close'] < dataframe['bb_lowerband2'])
        if self.buy_trigger.value == 'bb_lower3':
            conditions.append(dataframe['close'] < dataframe['bb_lowerband3'])

        conditions.append(dataframe['volume'] > 0)

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Buy strategy Hyperopt will build and use
        """
        conditions = []
        # GUARDS AND TRENDS
        if self.sell_rsi_enabled.value:
            conditions.append(dataframe['rsi'] > self.sell_rsi.value)

        # TRIGGERS

        if self.sell_trigger.value == 'sell-bb_lower1':
            conditions.append(dataframe['close'] > dataframe['bb_lowerband1'])
        if self.sell_trigger.value == 'sell-bb_middle1':
            conditions.append(dataframe['close'] > dataframe['bb_middleband1'])
        if self.sell_trigger.value == 'sell-bb_upper1':
            conditions.append(dataframe['close'] > dataframe['bb_upperband1'])
        #if self.sell_trigger.value == 'sell-bb_lower2':
        #    conditions.append(dataframe['close'] > dataframe['bb_lowerband2'])

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            'sell'] = 1
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
            Real(-0.5, -0.02, name='stoploss'),
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
    """
    @staticmethod
    def trailing_space() -> List[Dimension]:
        #Create a trailing stoploss space.
        #You may override it in your custom Hyperopt class.
        return [
            # It was decided to always set trailing_stop is to True if the 'trailing' hyperspace
            # is used. Otherwise hyperopt will vary other parameters that won't have effect if
            # trailing_stop is set False.
            # This parameter is included into the hyperspace dimensions rather than assigning
            # it explicitly in the code in order to have it printed in the results along with
            # other 'trailing' hyperspace parameters.
            CategoricalParameter([True], name='trailing_stop'),

            Real(0.01, 0.35, decimals=3, name='trailing_stop_positive'),

            # 'trailing_stop_positive_offset' should be greater than 'trailing_stop_positive',
            # so this intermediate parameter is used as the value of the difference between
            # them. The value of the 'trailing_stop_positive_offset' is constructed in the
            # generate_trailing_params() method.
            # This is similar to the hyperspace dimensions used for constructing the ROI tables.
            Real(0.001, 0.1, decimals=3, name='trailing_stop_positive_offset_p1'),

            CategoricalParameter([True, False], name='trailing_only_offset_is_reached'),
        ]
    """