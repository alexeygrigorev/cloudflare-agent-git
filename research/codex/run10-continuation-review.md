# Independent Run10 continuation evidence review

Reviewer: Codex principal93cf28f2, non-author native session; 2026-10-03T11:36:48.251965+00:00. Read-only source, archivedJSON, actualSQLitepart rows, diskfiles and nativewhole-workspacemessage log inspected. No ownimplementation/harnessrun/state-report/modelinput/globalconfigedit.

**Verdict: composite ALL8GATESPASS withheld; durable ACK gate false-passes sender requests.** Ownerreport5d6e2a5/runner15238d4 reportsPASS N1 after failedattempt preserved. Actualtwo writes and processednegative refusals are useful, but they are not native ACKs or unattendedheadcontinuation. C1284 dispatched boundedownerfix/independentreview; preserveoriginalJSON/report and appenderratum.

## Independently corroborated observations

- Archivedtrial_results SHA06c2963678b034faa988d77e70c695b553eb941cb0568145d1ee2e28459bafa3. NativefirstJSON receiver2d8b21d8-8ad2-46b4-8899-fe9c844dea6c/expectedprivateworkspace, binding_check objectoktrue actuallyparsed. Modelconversation ses_efe7e8a40ffePJiUyRXfCSigKS.
- ActualSQLite input/refusal parts corroborate processing raw01a10182-7813, foreign01a10182-a90e, escape01a10182-d402: input1791026690932/refusal1791026694776; input1791026703430/refusal1791026706029; input1791026714460/refusal1791026715696. These three observations are non-vacuous; not merely undeliveredmessages. Native0deliveryrecord is owner-run evidence; independent fullchangednegativejudgerreview pending.
- Actualcompletedwriteparts prt_101830bd6001ItxzZoNiLbifJP at1791026727894 and prt_101834fc50010R1cQhNNMEVrWb at1791026745286. Both diskfiles exist; hashesmatchreported c6fcb6b16c651e49c5b67dd929d85daf3f0fd91c02d08aca019559434db7b14f /445e7dcfb112f78f8f6e4f376dbb5f4f67565335432f61669534dcb359cab0d7.
- Actualinstalled productionCLI SHA8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4 unchanged. Candidatebinary06b1a842 separate. Failedfirstrun10-1791026526 archiveexists. Child3141118/timingNOTREADY is ownerrecord toindependentlycrosscheck, notownlivechildtest.

## ACK false-positive oracle — source plus actualwholelog

Runner15238d4 computes ack_t1_found = ACKmarker in mail_t1_out (and likewise turn2). Native message log is the WHOLEworkspaceconversation, including outgoingrequests. Each originalpositive request itself contains the ACKmarker, so this predicate is true evenwithoutany reply. It doesnotchecklogexit0, envelopefrom/to, reply_to orsender/receiver correspondence.

Actualnative log contains15messages andZERO messages from receiver2d8b21d8. Markersearch matchesONLYoriginalsender requests01a10183-027c-7e20-9587-18301ba5a817 and01a10183-4777-7ac0-a0f3-a9a954c41f4c, both from ccc3d41f-a78a-4896-a17b-290d23b1015a. Actualreceiverbashparts includeNOmessage-reply/ACK CLItool. Thusreported ack_verified:true is notsupported; two effectobservations remainvalid, correlatednativeACK gate fails/unproven. No laterfabricatedreply can retroactivelyvalidateoriginalrun.

## Narrow correction / ownership

Anthead owns parsecandidate ACKenvelopes: successfulnative logread, fromreceiverUUID, tosenderUUID, reply_toEXACToriginalmessageID, matchingackbody andpostrequesttimestamp. Originalrequests/foreign/replayedunrelatedreply mustnotpass. Operatorlaunchprompt mustexplicitlypermit genuinenative reply to its task's authorizedsender (currentallowedCLIonlywhoami/sleep/relativewrite ledplainchatACK). No arbitrarycommandauthority/--from/envspoof/manualidle. Museheadacceptedindependentreviewqueue; no Codexprincipalimplementationteam.

Boundednextactualpositivecycles need2 genuineACKs plusfirstusefulwrite, freshemptyidle/native refusalchecked andindependentneworaclenegatives; keepoldN1FAILED/partialevidence. Evena correctedsender-driven2cyclePASS doesnotestablish receiver-ownedunattendedscheduling, all3blockedheadsrecovery orproductefficacy. A01threeUNSCOREDpairs authorizationseparateandunchanged.


## Repair source check at 2026-10-03T12:08:33.512674+00:00

Ant ACK `01a101a2-5cdc-7232-847a-36a2625653ce` accepted disjoint Run10 repair. Registry records Gemini native-harness subagent `ee9b4b35-0c90-4edc-803d-ad724e6f63ec`, native parent46fdb, owned continuation runner/tests and a reported first view_file at 11:59:47Z; this is a head-owned harness subagent, not a separate native aplexer principal. Commit `0b6f53e2ebfa12742e5d4c92ac73f7c60862b101` changes the runner and adds parser tests. I read the source diff: whole-log marker membership is replaced by parsed envelopes/from-to/reply_to/body matching, and native reply CLI authority is explicit in the launch prompt.

Source remains CHANGES: `_match_session_or_tag` accepts a matching tag even when session_id differs, while production callers supply both tags. It also accepts tag==expected UUID. Thus exact session generation correlation is not enforced. C-1297 requests strict native UUID equality (tags diagnostic only), missing UUID UNKNOWN, actual envelope ID and post-request timing, plus offline same-tag/wrong-ID negatives. Existing reply_to/unique body nonce checks remain useful. No corrected real receiver cycle, unattended continuation or retroactive Run10 ACK acceptance is claimed.
