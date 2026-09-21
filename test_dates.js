const b_branch_last_updated = "2026-09-18T14:22:02";
const preRelease_created = "2026-09-15T11:20:38.962593";

const lastUpdated = new Date(b_branch_last_updated).getTime();
const latestReleaseTime = new Date(preRelease_created).getTime();

console.log("lastUpdated:", lastUpdated);
console.log("latestReleaseTime:", latestReleaseTime);
console.log("lastUpdated > latestReleaseTime:", lastUpdated > latestReleaseTime);
