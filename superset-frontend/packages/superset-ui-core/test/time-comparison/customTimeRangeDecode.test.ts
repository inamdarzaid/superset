import { customTimeRangeDecode } from '@superset-ui/core';

describe('customTimeRangeDecode', () => {
  it('should decode specific : specific', () => {
    const { customRange } = customTimeRangeDecode(
      '2021-01-20T00:00:00 : 2021-01-28T00:00:00',
    );
    expect(customRange.sinceDatetime).toEqual('2021-01-20T00:00:00');
    expect(customRange.untilDatetime).toEqual('2021-01-27T00:00:00');
    expect(customRange.sinceMode).toEqual('specific');
    expect(customRange.untilMode).toEqual('specific');
  });

  it('should decode specific : relative', () => {
    const { customRange } = customTimeRangeDecode(
      '2021-01-20T00:00:00 : DATEADD(DATETIME("2021-01-20T00:00:00"), 7, day)',
    );
    expect(customRange.sinceDatetime).toEqual('2021-01-20T00:00:00');
    expect(customRange.untilGrain).toEqual('day');
    expect(customRange.untilGrainValue).toEqual(7);
    expect(customRange.sinceMode).toEqual('specific');
    expect(customRange.untilMode).toEqual('relative');
  });

  it('should decode relative : specific', () => {
    const { customRange } = customTimeRangeDecode(
      'DATEADD(DATETIME("2021-01-28T00:00:00"), -7, day) : 2021-01-28T00:00:00',
    );
    expect(customRange.sinceGrain).toEqual('day');
    expect(customRange.sinceGrainValue).toEqual(-7);
    expect(customRange.untilDatetime).toEqual('2021-01-27T00:00:00');
    expect(customRange.sinceMode).toEqual('relative');
    expect(customRange.untilMode).toEqual('specific');
  });

  it('should decode relative : relative', () => {
    const { customRange } = customTimeRangeDecode(
      'DATEADD(DATETIME("now"), -7, day) : DATEADD(DATETIME("now"), 7, day)',
    );
    expect(customRange.sinceGrain).toEqual('day');
    expect(customRange.sinceGrainValue).toEqual(-7);
    expect(customRange.untilGrain).toEqual('day');
    expect(customRange.untilGrainValue).toEqual(7);
    expect(customRange.anchorValue).toEqual('now');
    expect(customRange.sinceMode).toEqual('relative');
    expect(customRange.untilMode).toEqual('relative');
  });

  it('should return default custom range for empty string', () => {
    const { matchedFlag } = customTimeRangeDecode('');
    expect(matchedFlag).toBe(false);
  });

  it('should return default custom range for undefined:undefined', () => {
    const { matchedFlag } = customTimeRangeDecode('undefined : undefined');
    expect(matchedFlag).toBe(false);
  });

  it('should return default custom range for undefined:now', () => {
    const { matchedFlag } = customTimeRangeDecode('undefined : now');
    expect(matchedFlag).toBe(false);
  });
});