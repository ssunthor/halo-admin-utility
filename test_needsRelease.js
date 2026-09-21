const project = {
    inventory: {
        pre_releases: [
            { created_at: "2026-09-15T11:20:38.962593" }
        ]
    }
};
const b = {
    branch: 'dev',
    branch_last_updated: "2026-09-18T14:22:02"
};

const isCoreEnv = b.branch === 'dev' || b.branch === 'main' || b.branch === 'master';
const lastUpdated = new Date(b.branch_last_updated || 0).getTime();

let needsRelease = false;
if (isCoreEnv) {
    let latestReleaseTime = 0;
    if (b.branch === 'dev') {
        const preReleases = project.inventory?.pre_releases || [];
        if (preReleases.length > 0) {
            latestReleaseTime = new Date(preReleases[0].created_at || preReleases[0].container_created || 0).getTime();
        }
    } else {
        const releases = project.inventory?.releases || [];
        if (releases.length > 0) {
            latestReleaseTime = new Date(releases[0].created_at || releases[0].container_created || 0).getTime();
        }
    }
    needsRelease = latestReleaseTime === 0 || lastUpdated > latestReleaseTime;
}

console.log("needsRelease:", needsRelease);
