import React, { useEffect, useRef } from 'react';

/**
 * Symbol mapping from internal bot symbols to official TradingView ticker identifiers
 */
function mapToTradingViewSymbol(sym) {
    if (!sym) return 'BINANCE:BTCUSDT';
    const clean = sym.toUpperCase().trim();
    if (clean.includes('BTC')) return 'BINANCE:BTCUSDT';
    if (clean.includes('PAXG') || clean.includes('GOLD') || clean.includes('GC')) return 'BINANCE:PAXGUSDT';
    if (clean.includes('ETH')) return 'BINANCE:ETHUSDT';
    if (clean.includes('EUR')) return 'FX:EURUSD';
    if (clean.includes('SOL')) return 'BINANCE:SOLUSDT';
    return `BINANCE:${clean.replace('/', '')}`;
}

/**
 * Maps timeframe strings to TradingView interval codes
 */
function mapToTradingViewInterval(tf) {
    if (!tf) return '1';
    switch (tf.toLowerCase()) {
        case '1s': return '1S';
        case '5s': return '5S';
        case '15s': return '15S';
        case '30s': return '30S';
        case '1m': return '1';
        case '5m': return '5';
        case '15m': return '15';
        case '30m': return '30';
        case '1h': return '60';
        case '4h': return '240';
        case '1d': return 'D';
        case '1w': return 'W';
        default: return '1';
    }
}

export const ChartWidget = ({ symbol = 'BTC/USDT', timeframe = '1s', height = '580px' }) => {
    const containerRef = useRef(null);
    const containerId = useRef(`tv_chart_${Math.random().toString(36).substring(2, 9)}`);

    useEffect(() => {
        const tvSymbol = mapToTradingViewSymbol(symbol);
        const tvInterval = mapToTradingViewInterval(timeframe);

        const initWidget = () => {
            if (window.TradingView && containerRef.current) {
                containerRef.current.innerHTML = '';
                new window.TradingView.widget({
                    autosize: true,
                    symbol: tvSymbol,
                    interval: tvInterval,
                    timezone: "Etc/UTC",
                    theme: "dark",
                    style: "1",
                    locale: "en",
                    toolbar_bg: "#090d16",
                    enable_publishing: false,
                    allow_symbol_change: true,
                    container_id: containerId.current,
                    hide_side_toolbar: false,
                    withdateranges: true,
                    save_image: true,
                    details: false,
                    hotlist: false,
                    calendar: false,
                    studies: [
                        "RSI@tv-basicstudies",
                        "MASimple@tv-basicstudies",
                        "MACD@tv-basicstudies"
                    ],
                    overrides: {
                        "paneProperties.background": "#090d16",
                        "paneProperties.vertGridProperties.color": "rgba(255, 255, 255, 0.05)",
                        "paneProperties.horzGridProperties.color": "rgba(255, 255, 255, 0.05)",
                        "mainSeriesProperties.candleStyle.upColor": "#10b981",
                        "mainSeriesProperties.candleStyle.downColor": "#ef4444",
                        "mainSeriesProperties.candleStyle.borderUpColor": "#10b981",
                        "mainSeriesProperties.candleStyle.borderDownColor": "#ef4444",
                        "mainSeriesProperties.candleStyle.wickUpColor": "#10b981",
                        "mainSeriesProperties.candleStyle.wickDownColor": "#ef4444"
                    }
                });
            }
        };

        if (window.TradingView) {
            initWidget();
        } else {
            const script = document.createElement('script');
            script.src = 'https://s3.tradingview.com/tv.js';
            script.async = true;
            script.onload = initWidget;
            document.head.appendChild(script);
        }
    }, [symbol, timeframe]);

    return (
        <div style={{
            position: 'relative',
            width: '100%',
            height: height,
            background: '#090d16',
            borderRadius: '12px',
            overflow: 'hidden',
            border: '1px solid rgba(255, 255, 255, 0.08)'
        }}>
            <div 
                id={containerId.current} 
                ref={containerRef} 
                style={{ width: '100%', height: '100%' }}
            />
        </div>
    );
};
