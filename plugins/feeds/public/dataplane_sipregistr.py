import logging
from datetime import datetime, timedelta

import pandas as pd
from core.errors import ObservableValidationError
from core.feed import Feed
from core.observables import AutonomousSystem, Ip


class DataplaneSIPRegistr(Feed):
    '''
       Feed of SIP registr with IPs and ASNs
    '''
    default_values = {
        "frequency": timedelta(hours=2),
        "name": "DataplaneSIPRegistr",
        "source": "https://dataplane.org/sipregistration.txt",
        "description": "Entries below consist of fields with identifying characteristics of a source IP address that has been seen initiating a SIP REGISTER operation to a remote host.",
    }

    def update(self):
        resp = self._make_request(sort=False)
        lines = resp.content.decode("utf-8").split("\n")[64:-5]
        columns = ["ASN", "ASname", "ipaddr", "lastseen", "category"]
        df = pd.DataFrame([l.split("|") for l in lines], columns=columns)

        for c in columns:
            df[c] = df[c].str.strip()
        df = df.dropna()
        df["lastseen"] = pd.to_datetime(df["lastseen"])
        if self.last_run:
            df = df[df["lastseen"] > self.last_run]
        for count, row in df.iterrows():
            self.analyze(row)

    def analyze(self, row):

        context_ip = {
            "source": self.name,
            "last_seen": row["lastseen"],
            "date_added": datetime.utcnow(),
        }

        try:
            ip = Ip.get_or_create(value=row["ipaddr"])
            ip.add_context(context_ip, dedup_list=["date_added"])
            ip.add_source(self.name)
            ip.tag("dataplane")
            ip.tag("sip")
            ip.tag(row["category"])

            asn = AutonomousSystem.get_or_create(value=row["ASN"])
            context_ans = {"source": self.name, "name": row["ASname"]}
            asn.add_context(context_ans, dedup_list=["date_added"])
            asn.add_source(self.name)
            asn.tag("dataplane")
            asn.active_link_to(ip, "AS", self.name)
        except ObservableValidationError as e:
            logging.error(e)
