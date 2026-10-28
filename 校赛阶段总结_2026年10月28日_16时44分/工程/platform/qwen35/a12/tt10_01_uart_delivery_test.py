"""Regression: delayed authentication must not send reboot code after UART expiry."""
import copy,datetime,json
from tt10_01_transport import require_fresh_uart
now=datetime.datetime(2026,10,25,tzinfo=datetime.timezone.utc)
good=dict(schema='A10_ONE_MANUAL_COLD_IRQ2_BOOT_V1',closed=False,
          status='ARMED_PASSIVE_WAIT_FOR_USER_POWER',boot_commands_sent=0,autoboot_stop_bytes_sent=0,
          events=[dict(kind='armed',utc=(now-datetime.timedelta(seconds=60)).isoformat())])
assert require_fresh_uart(good,now)==60
checks=1
for field,value in [('closed',True),('status','STOPPED'),('boot_commands_sent',1),
                    ('autoboot_stop_bytes_sent',1),('schema','wrong')]:
    bad=copy.deepcopy(good);bad[field]=value
    try:require_fresh_uart(bad,now)
    except AssertionError:checks+=1
    else:raise AssertionError(field)
for seconds in (-1,181,300):
    bad=copy.deepcopy(good);bad['events'][0]['utc']=(now-datetime.timedelta(seconds=seconds)).isoformat()
    try:require_fresh_uart(bad,now)
    except AssertionError:checks+=1
    else:raise AssertionError('expired/future arm accepted')
print(json.dumps(dict(status='PASS_PC_UART_DELIVERY_GUARDS',checks=checks,board_contact=False)))
