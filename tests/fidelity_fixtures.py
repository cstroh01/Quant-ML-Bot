"""Synthetic Fidelity-shaped CSV exports (spec 054). EXAMPLE — NOT A RESULT.

Kept as strings because the repository ignores *.csv. CRLF line endings match real exports.
"""

POSITIONS = 'Account Number,Account Name,Symbol,Description,Quantity,Last Price,Last Price Change,Current Value,Today\'s Gain/Loss Dollar,Today\'s Gain/Loss Percent,Total Gain/Loss Dollar,Total Gain/Loss Percent,Percent Of Account,Cost Basis Total,Average Cost Basis,Type\r\nZ00000000,Individual,SPAXX**,HELD IN MONEY MARKET,,,,$49.00,,,,,49.00%,,,Cash,\r\nZ00000000,Individual,EXMP,EXAMPLE ETF,2,$25.75,+$0.25,$51.50,+$0.50,+0.98%,+$0.50,+0.98%,51.00%,$51.00,$25.50,Cash,\r\nZ00000000,Individual,Pending Activity,,,,,$0.00,,,,,,,,,\r\n\r\n"The data and information in this spreadsheet is provided to you solely for your use. EXAMPLE — NOT A RESULT."\r\n\r\n"Date downloaded Oct-07-2026 10:45 p.m ET"\r\n'

HISTORY = '\r\n\r\nRun Date,Action,Symbol,Description,Type,Price ($),Quantity,Commission ($),Fees ($),Accrued Interest ($),Amount ($),Cash Balance ($),Settlement Date\r\n09/25/2026,Electronic Funds Transfer Received (Cash),"",No Description,Cash,"",0,"","","",100,100,""\r\n10/01/2026,YOU BOUGHT EXAMPLE ETF (EXMP) (Cash),EXMP,EXAMPLE ETF,Cash,25.5,2,"","","",-51,49,10/02/2026\r\n\r\n"The data and information in this spreadsheet is provided to you solely for your use and is not for distribution. EXAMPLE — NOT A RESULT."\r\n\r\nDate downloaded 10/07/2026 10:41 pm\r\n'
