from itertools import groupby, chain, repeat
import operator

from django.http import HttpResponse
from django.shortcuts import render
from django.template import RequestContext
from django.shortcuts import redirect

from replay_parser import replayCompile, statCollector

AGGREGATED_FORMS = {"Arceus-*", "Pumpkaboo-*", "Rotom-Appliance"}
TIERS = ["RBY","GSC","ADV","DPP","BW","ORAS","SM"]

def index(request):
	if request.method == "GET":
		return render(request, "index.html")
		
	if request.method == "POST":
		if "link_submit" in request.POST:
			tiers = [] #refactor
			urls = request.POST["replay_urls"].split("\n")
			replays = replayCompile.replays_from_links(urls)
			
		if "thread_submit" in request.POST:
			if not request.POST["tier"]:
				tiers = {"gen7pokebankou"}
			else:
				tiers = {tier.strip() for tier in
						 request.POST["tier"].split(",")}
			url = request.POST["url"]
			replays = (replayCompile.replays_from_thread(url, tiers=tiers,
			start=int(request.POST["start"]) if request.POST["start"] else 1,
			end=int(request.POST["end"]) if request.POST["end"] else None)
			| replayCompile.replays_from_links(request.POST["additional"]
			  .split("\n")))
			
		if "range_submit" in request.POST:
			if not request.POST["tier"]:
				tier = "gen7pokebankou"
			else:
				tier = request.POST["tier"]
			replays = replayCompile.replays_from_range(
					  				range(int(request.POST["start"]),
					  				int(request.POST["end"])),
					  				tier=tier)
		# Tier
		# move to replays
		try:
			gen_num = next((char for char in min(tiers) if char.isdigit()), 6)
			tier_name = min(tiers).split(gen_num)[1].split("pokebank")[-1].upper()
			tier_label = TIERS[int(gen_num)-1] + " " + tier_name
		except:
			tier_label = "???"
		
		# Stats
		cumulative = (statCollector.stats_from_text(request.POST["stats"]) 
					  #if "stats" in request.POST else None)
					  if request.POST["stats"] else None)
		missing = chain.from_iterable((((replay.playerwl[wl],6-len(replay.teams[wl])) for wl in replay.teams if len(replay.teams[wl]) < 6) for replay in replays))
		usage_table = usage(replays, tiers, cumulative)
		whitespace_table = whitespace(usage_table['usage'])
		return render(request, "stats.html", 
					 {"usage_table" : usage_table['usage'],
					  "whitespace" : whitespace_table,
					  "net_mons" : usage_table['net_mons'],
					  "net_replays" : usage_table['net_replays'],
					  "missing":missing,
					  "tier_label":tier_label})

def spl_index(request):
	if request.method == "GET":
		return render(request, "spl_index.html")
		
	if request.method == "POST":
		if "link_submit" in request.POST:
			urls = request.POST["replay_urls"].split("\n")
			replays = replayCompile.replays_from_links(urls)
		else:
			replays = replayCompile.replays_from_user(request.POST["player"],tier=request.POST["tier"])

		moves = [replay.get_moves() for replay in replays]
		
		# Overall Stats
		usage_table = usage(replays)
		whitespace_table = whitespace(usage_table)
		
		# Raw
		raw = (
			"\n\n---\n\n".join([
			"\n\n".join([
			player.capitalize() + ": " + replay.playerwl[player] + "\n"
			+ "\n".join([pokemon + ": " 
			+ " / ".join([move for move in replay.moves[player][pokemon]])
			for pokemon in replay.moves[player]])
			for player in ("win","lose")])
			for replay in replays]))
		row_count = len(replays) * 18 - 2
		
		# Set not removing duplicates
		return render(request, "spl_stats.html", {
					"usage_table" : usage_table,
					"whitespace" : whitespace_table,
					"replays" : replays,
					"raw":raw,
					"row_count":row_count})

def usage(replays, tiers = [], cumulative = None):
	usage = statCollector.usage(replays)
	wins = statCollector.wins(replays)
	total = len(replays) * 2
	if "gen4ou" in tiers:
		usage.update(list(chain.from_iterable(
		("Rotom-Appliance" for i in range(usage[poke]))
		for poke in usage if poke.startswith("Rotom-"))))
		
		wins.update(list(chain.from_iterable(
		("Rotom-Appliance" for i in range(wins[poke]))
		for poke in usage if poke.startswith("Rotom-"))))
		
	if cumulative:
		usage.update(cumulative["usage"])
		wins.update(cumulative["wins"])
		total += cumulative["total"]

		
	sorted_usage = sorted(usage.most_common(), 
						  key=lambda x: (usage[x[0]], float(wins[x[0]])/x[1]),
						  reverse=True) 
	
	# Calculate rank? Accumulate the length of the groups preceding the group
	'''
	rankings = chain.from_iterable(
			   ((rank, len(element[1])) for rank, element in
			   enumerate(groupby(usage.most_common(), lambda x: x[1]), 1)))'''
			   
	# Number of Pokemon with same ranking
	counts = [len(list(element[1])) for element in groupby(
			 [poke for poke in sorted_usage if poke[0] not in AGGREGATED_FORMS],
			 lambda x: x[1])]
	# Translate to rankings
	unique_ranks = accumulate([1] + counts[:-1:])
	# Unpack rankings
	rankings = chain.from_iterable([rank for i in xrange(0,count)] 
									for rank, count in zip(unique_ranks, counts))
	
	return {'usage': [(
				element[0], 
			 	element[1], 
			 	"{0:.2f}%".format(100 * float(element[1])/total),
			 	"{0:.2f}%".format(100 * float(wins[element[0]])/element[1]),
			 	str(next(rankings)) if element[0] not in AGGREGATED_FORMS else "-")
			 	for i, element in enumerate(sorted_usage)],
			 'net_mons':sum(usage.values()),
			 'net_replays':len(replays)
			}
			 
			 

def whitespace(usage_table):
	return [(
			entry[0] + " " * (18 - len(entry[0])), 
			" " * (3 - len(str(entry[1]))) + str(entry[1]), 
			" " * (7 - len(str(entry[2]))) + str(entry[2]),
			" " * (7 - len(str(entry[3]))) + str(entry[3]),
			entry[4] + " " * (4-len(entry[4]))
			)
			for rank, entry in enumerate(usage_table, 1)]
	
def accumulate(iterable, func=operator.add):
	''' Raw code for accumulate function (not available prior to Python 3) '''
	it = iter(iterable)
	total = next(it)
	yield total
	for element in it:
		total = func(total, element)
		yield total
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
'''
def index(request):
	if request.method == "GET":
		return render(request, "index.html")

	if request.method == "POST":
		start = request.POST["start"]
		end = request.POST["end"]
		url = request.POST["url"]
		rng = range(int(start), int(end))
		pairings = tournament.parsePairings(url = url)
		participants = tournament.participantsFromPairings(pairings)
		tour = tournament.Tournament(
			   replayCompile.replaysFromRange(rng), pairings, participants)
		replays = tour.matchTournament()
		matches = tour.pairingReplayMap
		return render(request, "results.html", {
		#return redirect('/replays/', {
			"start" : start,
			"end" : end,
			"url" : url,
			#"pairings" : pairings,
			"participants" : participants,
			"matches" : [(str(pairing).strip("frozenset"), 
						  matches[pairing][0].number, 
						  matches[pairing][0].players,
						  matches[pairing][1],
						  matches[pairing][0].url) if pairing in matches 
						  else (
						  (str(pairing).strip("frozenset")), "", "", "No match found") 
						  for pairing in pairings]
		})'''