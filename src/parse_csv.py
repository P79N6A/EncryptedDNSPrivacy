from google.cloud import bigquery
import json, time
import os, sys, requests
from urllib.parse import urlparse
from datetime import datetime
from difflib import SequenceMatcher

today = str(datetime.now()).split(' ')[0]
print("Run on: ", today)

if len(sys.argv) != 2:
    print("Enter in the format: python3 parse_csv.py <file> -- <file> should be in the format ../input/filename")
    exit()

csvfile = sys.argv[1] 
alias = csvfile.split(".csv")[0].split("/")[-1]

rankings = dict()
with open("alexa.csv") as alexa:
    for row in alexa:
        row = row.split(",")
        rankings[row[1].strip('\n')] = int(row[0].strip('\n'))
            
cdn_map = []
with open('cnamechain.json') as f:
    cdn_map = json.load(f)

def get_cdn(answer, cdn_map):
    lengths = []
    for key in cdn_map:
        match = SequenceMatcher(None, key[0], answer).find_longest_match(0, len(key[0]), 0, len(answer))
        lengths.append(len(key[0][match.a: match.a + match.size]))
    maxLen = max(lengths)
    index = lengths.index(maxLen)
    return cdn_map[index][1]

ip_to_domains = dict()
ip_to_sites = dict()
domain_to_resources = dict()
domain_to_cdn = dict()
domain_to_site = dict()

filename = "domainlist_" + alias
domainlist = open(filename, "w+")

with open(csvfile) as csvfiledata:
    for row in csvfiledata:
        row = row.split(',')
        try:  
            url = urlparse(row[3].strip('\n'))
            domain = url.netloc
            try:
                rank = rankings[domain]
                if rank > 10000:
                    continue
            except KeyError:
                continue
            if (len(domain)) == 0:
                continue
            site = row[1].strip('\n')
            resource = row[4].strip('\n')
            if len(resource) > 10:
                continue
            print(domain, resource)
            try:
                s = domain_to_site[domain]
            except KeyError:
                line = domain.strip('\n') + "\n"
                domainlist.write(line)
            domain_to_site.setdefault(domain, set()).add(site)            
            domain_to_resources.setdefault(domain, set()).add(resource)
        except Exception as e:
            print("Exception: ", e)
            exc_type, _, exc_tb = sys.exc_info()
            print(exc_type, exc_tb.tb_lineno, "\n\n")

domainlist.close()

# perform queries
print("STARTING ZDNS\n")
cmd =  'cat ' + filename + ' | ~/go/bin/zdns A -retries 10'
output = os.popen(cmd).readlines()
for op in output:
    obj = json.loads(op)
    try:
        domain = obj['name']
        site = domain_to_site[domain]
        site = next(iter(site))
        if obj['status'] == 'NOERROR':
            answers = obj['data']['answers']
            for answer in answers:
                if answer["type"] == "CNAME":
                    answer_ret = answer["answer"]
                    cdn = get_cdn(answer_ret, cdn_map)
                    domain_to_cdn.setdefault(domain, set()).add(cdn)
                elif answer["type"] == "A":
                    ip = answer["answer"]
                    ip_to_domains.setdefault(ip, set()).add(domain)
                    ip_to_sites.setdefault(ip, set()).add(site)
        else:
            print(obj['name'], obj['status'])
    except Exception as e:
        print("Exception: ", e)
        exc_type, _, exc_tb = sys.exc_info()
        print(exc_type, exc_tb.tb_lineno, "\n\n")

count_unique = 0
with_cdn = 0
potential = 0

print("WRITING FINAL OUTPUT\n")
with open("../output/unique_"+str(alias)+"_"+today+".txt", "w") as f:
    for ip in ip_to_sites:
        if len(ip_to_sites[ip]) == 1:
            # here the ip is unique
            domains = ip_to_domains[ip]
            for domain in domains:
                count_unique += 1
                try:
                    cdn = domain_to_cdn[domain]
                    with_cdn += 1
                    line = next(iter(ip_to_sites[ip])) + "," + domain + "," +  ip + "," + str(domain_to_resources[domain])+ "," + str(domain_to_cdn[domain]) + "\n"
                    f.write(line)
                except KeyError:
                    potential += 1
                    line = next(iter(ip_to_sites[ip])) + "," + domain + "," +  ip + "," + str(domain_to_resources[domain]) + ", CDN missing \n"
                    f.write(line)
                
print("count_unique: ", count_unique)
print("cdn present: ", with_cdn)
print("potential: ", potential)

