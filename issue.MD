# SMS Receiver Website Scraping Plan

This document outlines the development plan for scraping various free SMS-receiving websites, categorized by priority and technical difficulty.

### Category 1: Core Targets (High Priority)
*These sites are simple, classic platforms, ideal for initial development.*
- [x] freereceivesms - `https://www.freereceivesms.com/` - A classic and straightforward free SMS receiver.
- [ ] SMS Receive Free - `https://smsreceivefree.com/` - Features a clean table-based layout, easy to parse.
- [ ] Receive-SMS - `https://receive-sms.com/` - A long-standing service with a simple, clear interface.
- [ ] Receive a SMS Online - `https://receive-a-sms.com/` - Intuitive design, typically without complex scripts.

### Category 2: Expansion Targets (Medium Priority)
*These sites may require advanced scraping techniques (e.g., browser automation) due to dynamic content or complex layouts.*
- [ ] My Trash Mobile - `https://zh.mytrashmobile.com/` - A multi-language service, may use JS to load content.
- [ ] Free Phone Num - `https://ch.freephonenum.com/` - Subdomain suggests country-specificity; requires investigation.
- [ ] Receive SMS Online for FREE - `https://www.receive-sms-online.info/` - A common platform type, might have heavy ads.
- [ ] Free SMS Numbers Online - `https://smsnumbersonline.com/` - Standard free SMS service, good for expanding number sources.
- [ ] Receive SMS online for Free - `https://sms-online.co/receive-free-sms` - Modern-looking UI, likely relies on JavaScript rendering.
- [ ] Receive FREE SMS online - `http://receivefreesms.com/` - A standard service, good for source expansion.
- [ ] RECEIVE SMS ONLINE - `https://www.receivesmsonline.net/` - Another common platform, structure may vary.
- [ ] Free Online Phone - `https://www.freeonlinephone.org/` - Generic free phone service, a good candidate for expansion.
- [ ] Receive SMS Online - `http://receive-sms-online.com/` - Similar to others, needs to be checked for structure.
- [ ] SELLAITE - `http://sms.sellaite.com/` - Features a legacy UI; needs to be checked if still active.
- [ ] receive-smss - `https://receive-smss.com/` - A standard public SMS receiver, appears to use a common URL structure.

### Category 3: Chinese-Specific Targets (Independent Module)
*Chinese-language sites that may have unique anti-scraping mechanisms. Best handled as a separate module.*
- [ ] xinghai - `https://xinghai.party/` - A Chinese platform for receiving SMS.
- [ ] xnsms - `https://www.xnsms.com/` - An SMS-receiving service targeted at Chinese users.
- [ ] jiemadi - `https://www.jiemadi.com/` - A popular Chinese platform for temporary numbers.

### Category 4: Out of Scope / To Be Excluded
*These are not public SMS-receiving websites and do not fit the project's goal.*
- [ ] Twilio - `https://www.twilio.com/` - A commercial developer API (PaaS), not a public list.
- [ ] TextNow - `https://www.textnow.com/` - A private number app that requires user registration.
- [ ] Textfree - `https://www.pinger.com/text-free/` - A private number app, similar to TextNow.
